"""Use existing idle worker capacity after local RAM admission refuses inference.

Only model inference moves. The original controller still owns permissions,
actions, cancellation and verification. No model acquisition or service recovery.
"""
import copy
import json
import time
from team_design import _BARBARA_CHAT


class PlanningCapacityUnavailable(RuntimeError):
    """Transient inference admission/transport failure, never an execution receipt."""
    status = 503


def remote_inference(payload, stop, workers=('Adam', 'Barbara')):
    from hermes_worker import Worker, CONTEXT
    import auxiliary_client as barbara
    from sandbox_guest import guest_exec
    failures = []
    targeted = len(workers) == 1
    if not workers or any(worker not in {'Adam', 'Barbara'} for worker in workers):
        raise ValueError('Unknown local planning worker')
    for worker in workers:
        if stop.is_set():
            raise RuntimeError('Planner cancelled before remote dispatch')
        try:
            if worker == 'Adam':
                client = Worker()
                # Do not wait behind known active work: try overflow capacity.
                status = client.status()
                deadline=time.monotonic()+120
                while targeted and status.get('backend_reachable') and status.get('active_runs') != 0 and time.monotonic()<deadline:
                    if stop.wait(1):raise RuntimeError('Cancelled while waiting for Adam')
                    status=client.status()
                if not status.get('backend_reachable') or status.get('active_runs') != 0:
                    raise RuntimeError('Adam not idle')
                with client.exclusive(stop, timeout=120 if targeted else 2):
                    status = client.status()
                    if not status.get('backend_reachable') or status.get('active_runs') != 0:
                        raise RuntimeError('Adam no longer idle')
                    model = client.active_model()
                    client.gpu_ready(model, recover=False)
                    request = _payload(payload, model, CONTEXT)
                    if stop.is_set():raise RuntimeError('Cancelled')
                    result = client.request('/api/chat', request, ollama=True, timeout=110)
            else:
                with barbara.dispatch_lease(stop, timeout=120 if targeted else 5):
                    barbara.prepare_dispatch(barbara.probe(), stop)
                    model = 'qwen3.5:4b'
                    request = _payload(payload, model, 16384)
                    if stop.is_set():raise RuntimeError('Cancelled')
                    raw = barbara.checked(guest_exec(['python3','-c',_BARBARA_CHAT],
                        stdin=json.dumps(request).encode(), timeout=110))
                    result = json.loads(raw)
            if stop.is_set():raise RuntimeError('Cancelled after inference')
            if result.get('model') != model or result.get('done') is not True or result.get('done_reason') == 'length':
                raise RuntimeError('Remote planner identity/completion not verified')
            return result, {'worker':worker,'model':model,'backend':'worker planner inference'}
        except Exception as exc:
            from agent_support import diagnostic
            failures.append(worker+': '+type(exc).__name__+': '+diagnostic(str(exc))[:300])
    raise PlanningCapacityUnavailable('No suitable worker planning capacity completed the request ('+', '.join(failures)+').')


def _payload(payload, model, context):
    request = copy.deepcopy(payload)
    request.update(
        model=model,
        stream=False,
        # Remote workers are controller planners. Hidden reasoning must not
        # consume the response budget and produce an empty assistant action.
        think=False,
    )
    request.setdefault('options', {})['num_ctx']=context
    return request
