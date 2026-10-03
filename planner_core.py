"""Shared inference boundary. Only model generation is safe to retry here.

Execution, delegation and verification belong to the durable project controller.
No background threads, services, model loading or state writes occur on import.
"""
import http.client
import json
import time
import urllib.error


class PlannerCancelled(InterruptedError):
    pass


class PlannerProtocolError(ValueError):
    pass


def retryable(error):
    status = getattr(error, 'status', getattr(error, 'code', None))
    if status is not None:
        return status in {408, 429, 500, 502, 503, 504}
    return isinstance(error, (TimeoutError, ConnectionError, urllib.error.URLError,
                              http.client.IncompleteRead, http.client.RemoteDisconnected,
                              PlannerProtocolError, json.JSONDecodeError))


def generate(call, stopped=lambda: False, *, attempts=3, on_retry=None, wait=None):
    """Retry inference only; never rerun an execution callback after ambiguity."""
    if attempts < 1:
        raise ValueError('Generation requires a positive attempt budget')
    for attempt in range(attempts):
        if stopped():
            raise PlannerCancelled('Stopped at your request.')
        try:
            result = call()
            if stopped():
                raise PlannerCancelled('Stopped at your request.')
            return result
        except Exception as error:
            if stopped():
                raise PlannerCancelled('Stopped at your request.') from None
            if not retryable(error) or attempt + 1 == attempts:
                raise
            if on_retry:
                on_retry(attempt + 1, error)
            delay = min(2 ** attempt, 4)
            if wait is not None:
                wait(delay)
            else:
                deadline = time.monotonic() + delay
                while time.monotonic() < deadline:
                    if stopped():
                        raise PlannerCancelled('Stopped at your request.')
                    time.sleep(min(.1, max(0, deadline - time.monotonic())))


def response_object(value):
    if not isinstance(value, dict):
        raise PlannerProtocolError('Planner response must be an object')
    if value.get('error'):
        raise PlannerProtocolError('Planner returned an error envelope')
    return value


def read_response(response, *, streamed=False, stopped=lambda: False,
                  first_token=None, max_bytes=2 * 1024 * 1024, deadline_seconds=180):
    """Bound bytes and wall time, validate every record, require stream completion.

    Socket timeout remains the upper bound on cancellation during a blocked read.
    Never return partial content or partial tool arguments as an executable action.
    """
    deadline = time.monotonic() + deadline_seconds
    content, calls = [], []
    used = 0
    first = True
    while True:
        if stopped():
            raise PlannerCancelled('Stopped at your request.')
        if time.monotonic() >= deadline:
            raise TimeoutError('Planner response deadline exceeded')
        chunk = response.readline(min(max_bytes - used + 1, 1024 * 1024)) if streamed else response.read(max_bytes + 1)
        used += len(chunk)
        if used > max_bytes:
            raise PlannerProtocolError('Planner response exceeded its size limit')
        if not chunk:
            raise PlannerProtocolError('Planner response ended before completion')
        value = response_object(json.loads(chunk))
        if not streamed:
            return value
        message = value.get('message', {})
        if not isinstance(message, dict):
            raise PlannerProtocolError('Planner stream message must be an object')
        text, tools = message.get('content', ''), message.get('tool_calls', [])
        if not isinstance(text, str) or not isinstance(tools, list):
            raise PlannerProtocolError('Planner stream content or calls have invalid types')
        if text:
            content.append(text)
            if first and first_token:
                first_token()
            first = False
        calls.extend(tools)
        if value.get('done') is True:
            value['message'] = {'role': 'assistant', 'content': ''.join(content), 'tool_calls': calls}
            return value
