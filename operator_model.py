"""Native planner dialogue: retain actual calls and controller results together.

The controller owns authority, execution and verification. This adapter only
translates the model protocol; returning prose cannot finish an operation.
"""
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

from operator_runtime import CapabilityUnavailable, native_operator_action, operator_tools
from planner_core import read_response, response_object


class NativePlanner:
    def __init__(self, model, endpoint='http://127.0.0.1:11434/api/chat', *,
                 context=16384, request=None, instructions='', think=False, output_tokens=4096, fallback_request=None):
        self.fallback_request = fallback_request
        self.model, self.endpoint, self.context = model, endpoint, context
        self.request = request or self._request
        self.instructions = instructions
        self.think, self.output_tokens = think, output_tokens
        self.history = []
        self.pending = None

    def _request(self, payload):
        try:
            admit_local_model(self.model, self.endpoint)
        except CapabilityUnavailable as first:
            parsed = urllib.parse.urlparse(self.endpoint)
            local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}

            if local:
                try:
                    # A qualified GPU-resident model can be safe even when the
                    # conservative cold host-RAM estimate refuses loading it.
                    # Warm only an already-installed localhost model, then run
                    # the normal admission guard again. Never bypass admission.
                    warm_local_model(self.model, self.endpoint)
                    admit_local_model(self.model, self.endpoint)
                except Exception:
                    if self.fallback_request is None:
                        raise first
                    return self.fallback_request(payload)
            else:
                if self.fallback_request is None:
                    raise
                return self.fallback_request(payload)

        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return read_response(response)

    def _protocol_recovery_payload(self, payload, messages, allowed_names, error):
        """One compact retry after a malformed native planner response."""
        repaired = dict(payload)
        repaired["messages"] = [
            payload["messages"][0],
            {
                "role": "system",
                "content": (
                    "PROTOCOL RECOVERY: The previous response was invalid: "
                    + str(error)[:300]
                    + ". Call exactly ONE currently supplied tool now. "
                      "Use the supplied native tool schema EXACTLY; do not invent generic "
                      "tool or target fields. In particular, execute requires exactly "
                      "step=<an existing accepted plan step id> and command=<shell command>; "
                      "the controller derives the execution target from that step. "
                      "Never send tool=terminal or target=Otho inside an execute call. "
                      "write_file likewise uses step, path and content. "
                      "Do not return prose, empty content, multiple calls, or hidden reasoning. "
                      "For read actions use one direct nonmutating command only: no pipes, "
                      "redirection, shell chaining, grep pipelines, scripts, or secret reads. "
                      "If the accepted plan already contains the needed observations, advance "
                      "with an allowed execute/write_file action instead of rediscovering state. "
                      "Preserve the original objective and controller evidence. "
                      "Allowed tool names: " + ", ".join(sorted(allowed_names))
                ),
            },
            messages[-1],
        ]
        repaired["think"] = False
        repaired.setdefault("options", {})["temperature"] = 0
        repaired["options"]["num_predict"] = min(
            int(repaired["options"].get("num_predict", 1024)),
            1024,
        )
        return repaired

    def __call__(self, messages):
        context, _ = json.JSONDecoder().raw_decode(messages[-1]['content'])
        if self.pending is not None:
            evidence = context.get('recent_evidence', [])
            result = json.dumps(evidence[-1] if evidence else {'error':'No controller result available'})
            assistant = self.pending
            self.history.append(assistant)
            calls = assistant.get('tool_calls') or []
            if calls:
                for call in calls:
                    self.history.append({'role':'tool', 'tool_name':call['function']['name'], 'content':result})
            else:
                self.history.append({'role':'user','content':'Controller result: '+result})
            self.pending = None
            # Retain complete assistant/result pairs; this implementation admits
            # one action each turn, so the suffix cannot split a native pair.
            self.history = self.history[-12:]
            while self.history and len(json.dumps(self.history)) > 18000:
                self.history = self.history[2:]
        system = messages[0]['content'].replace('One JSON action per turn, no markdown.',
                                               'Call exactly one supplied native action per turn.')
        tools = operator_tools(messages)
        allowed_names = {tool['function']['name'] for tool in tools}
        system += ('\nCurrent controller phase permits ONLY these tools: '
                   + ', '.join(sorted(allowed_names))
                   + '. General action examples above do not enable other tools. '
                     'A rejected plan creates no steps; correct the plan before using a step. '
                     'Verification only observes existing results; it cannot run nmap, scripts or shells. '
                     'If the goal requires a capability excluded by the current contract/tools, '
                     'use blocked with that concrete reason, never fabricate an artifact or completed work.')
        if context.get('read_only_delegation'):
            system += '\n' + context['read_only_delegation']
        if context.get('contract_mode'):
            system += '\nContract mode: ' + str(context['contract_mode'])
        if context.get('mutation_authority'):
            system += '\n' + str(context['mutation_authority'])
        payload = {'model':self.model, 'messages':[{'role':'system','content':system+'\n'+self.instructions},
                    *self.history, messages[-1]], 'tools':tools,
                   'stream':False, 'think':self.think,
                   'options':{'num_ctx':self.context,'num_predict':self.output_tokens,'temperature':0}}
        try:
            data = response_object(self.request(payload))
        except urllib.error.HTTPError as error:
            if error.code not in {400, 413, 422} or not self.history:
                raise
            # Repair only the optional dialogue history; retain the original
            # objective, current evidence and exact controller tool schemas.
            payload['messages'] = [payload['messages'][0], messages[-1]]
            self.history = []
            data = response_object(self.request(payload))
        from agent_support import diagnostic
        message = data.get('message') or {}
        public = {key: value for key, value in message.items()
                  if key in {'role', 'content', 'tool_calls'}} if isinstance(message, dict) else {}
        def invalid(error):
            return json.dumps({'action': 'invalid', 'protocol_error': error,
                               'rejected_response': diagnostic(public)})
        if data.get('done_reason') == 'length':
            return invalid('Output truncated. Use smaller complete actions.')
        try:
            if not isinstance(message, dict):
                raise ValueError('Planner message must be an object')
            action = native_operator_action(message)
            if json.loads(action)['action'] not in allowed_names:
                raise ValueError('Action is unavailable in this phase; use only: '
                                 + ', '.join(sorted(allowed_names))
                                 + '. Rejected plans create no executable steps.')
        except (ValueError, KeyError, TypeError) as exc:
            # One bounded compact retry repairs occasional empty/prose/no-tool
            # native responses. Controller authority and tool schemas remain
            # unchanged; a second malformed response is returned as invalid.
            recovery_payload = self._protocol_recovery_payload(
                payload, messages, allowed_names, exc
            )
            try:
                recovered_data = response_object(self.request(recovery_payload))
                recovered_message = recovered_data.get('message') or {}
                if not isinstance(recovered_message, dict):
                    raise ValueError('Planner recovery message must be an object')
                action = native_operator_action(recovered_message)
                if json.loads(action)['action'] not in allowed_names:
                    raise ValueError(
                        'Recovered action is unavailable in this phase; use only: '
                        + ', '.join(sorted(allowed_names))
                    )
                message = recovered_message
            except (ValueError, KeyError, TypeError) as recovery_exc:
                return invalid(
                    'Protocol recovery failed after one retry: '
                    + str(recovery_exc)
                    + '. Original rejection: '
                    + str(exc)
                )

        # Store only the actual public call/content; no reasoning traces.
        self.pending = {key:value for key,value in message.items()
                        if key in {'role','content','tool_calls'}}
        self.pending.setdefault('role','assistant')
        return action



def warm_local_model(model, endpoint, *, keep_alive="30m", timeout=120):
    """Load an installed local Ollama model before conservative RAM admission.

    This is only for localhost Ollama. It does not acquire models, alter remote
    workers, or bypass admission. After warming, normal admit_local_model()
    still decides whether planning may proceed.
    """
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise CapabilityUnavailable("Local model warming requires a localhost Ollama endpoint")

    origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    with urllib.request.urlopen(origin + "/api/tags", timeout=5) as response:
        tags = read_response(response)

    if not any(row.get("name") == model for row in tags.get("models", [])):
        raise CapabilityUnavailable(
            "Planner model is not installed; acquire and qualify it before use"
        )

    payload = {
        "model": model,
        "prompt": "",
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"num_predict": 1},
    }

    request = urllib.request.Request(
        origin + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        read_response(response)

    with urllib.request.urlopen(origin + "/api/ps", timeout=5) as response:
        resident = read_response(response)

    if not any(row.get("name") == model for row in resident.get("models", [])):
        raise CapabilityUnavailable("Local planner warm-up completed but model is not resident")

    return True



def admit_local_model(model, endpoint, *, available_bytes=None, resident=None, model_bytes=None):
    """Conservative RAM admission after observed host OOM; not a memory guarantee.

    VRAM residency does not remove host allocations. Preserve host headroom and
    refuse a cold model whose weights plus reserve exceed measured available RAM.
    Remote worker admission belongs to that worker's qualified transport.
    """
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.hostname not in {'localhost','127.0.0.1','::1'}:
        return
    if available_bytes is None:
        values = dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        available_bytes = int(values['MemAvailable'].split()[0])*1024
    origin = urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,'','',''))
    def read(path):
        with urllib.request.urlopen(origin+path,timeout=5) as response:
            return read_response(response)
    if resident is None:
        resident = any(row.get('name') == model for row in read('/api/ps').get('models',[]))
    reserve = 3 * 1024**3
    if resident:
        needed = reserve
    else:
        if model_bytes is None:
            item = next((row for row in read('/api/tags').get('models',[]) if row.get('name') == model),None)
            if item is None:
                raise CapabilityUnavailable('Planner model is not installed; acquire and qualify it before use')
            model_bytes = item['size']
        needed = int(model_bytes * 1.1) + reserve
    if available_bytes < needed:
        raise CapabilityUnavailable('Insufficient measured host RAM for local planner with safety headroom; choose qualified remote capacity or a smaller tested model')
