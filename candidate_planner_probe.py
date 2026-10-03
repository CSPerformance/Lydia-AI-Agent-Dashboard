"""Supervised isolated candidate trial; never promotes or edits a worker default."""
from contextlib import contextmanager
import json
from pathlib import Path
import time

import auxiliary_client as client
from sandbox_guest import guest_exec
from operator_remote_sandbox_probe import main as trial

CANDIDATE = 'qwen3.5:9b'
# Official registry manifest prefix checked on 2026-09-24; fail on tag changes.
DIGEST_PREFIX = '6488c96fa5fa'
BASELINE = 'qwen3.5:4b'
CONTEXT = 16384
REPORT_PATH = Path('/tmp/lydia-candidate-planner-admission.json')


def remote_api(path, payload=None):
    if path not in {'/api/chat','/api/generate','/api/tags'}:
        raise ValueError('Unsupported candidate API')
    program = '''import json,sys,urllib.request
v=json.load(sys.stdin)
data=None if v['payload'] is None else json.dumps(v['payload']).encode()
r=urllib.request.Request('http://127.0.0.1:11434'+v['path'],data=data,headers={'Content-Type':'application/json'})
with urllib.request.urlopen(r,timeout=170) as response:print(json.dumps(json.load(response)))'''
    return json.loads(client.checked(guest_exec(['python3','-c',program],
        stdin=json.dumps({'path':path,'payload':payload}).encode(),timeout=180)))


def load(model, keep_alive='30m'):
    result = remote_api('/api/generate', {'model':model,'prompt':'','stream':False,
        'keep_alive':keep_alive,'options':{'num_ctx':CONTEXT}})
    if result.get('error'):
        raise RuntimeError('Candidate runtime request failed')


def require_candidate(sample, digest):
    client.require_qualified(sample)
    if sample.get('jobs', {}).get('exit_code') != 0 or sample['jobs'].get('output','').strip():
        raise RuntimeError('Worker activity changed during candidate trial')
    models = sample.get('models',{}).get('models',[])
    if len(models) != 1:
        raise RuntimeError('Candidate runner set changed')
    model = models[0]
    if (model.get('name') != CANDIDATE or model.get('digest') != digest or
            model.get('context_length') != CONTEXT or
            not isinstance(model.get('size'),int) or model['size'] <= 0 or
            model.get('size_vram',0) < model['size']):
        raise RuntimeError('Candidate is not pinned and fully GPU-resident at the test context')
    row = sample['gpu']['output'].strip().split(',')
    if len(row) != 4 or float(row[1])-float(row[2]) < 256:
        raise RuntimeError('Candidate leaves insufficient measured GPU headroom')


@contextmanager
def candidate_session():
    report = {'candidate':CANDIDATE,'baseline':BASELINE,'context':CONTEXT,'started':time.time(),
              'promoted':False,'restored':False}
    with client.dispatch_lease(timeout=5):
        before = client.probe()
        client.prepare_dispatch(before)
        client.require_ready(client.probe())
        tags = remote_api('/api/tags')['models']
        candidate = next((m for m in tags if m.get('name') == CANDIDATE),None)
        if not candidate or not candidate.get('digest','').startswith(DIGEST_PREFIX):
            raise RuntimeError('Candidate not downloaded or registry identity changed')
        digest = candidate['digest']
        report['digest'] = digest
        try:
            load(BASELINE, 0)
            load(CANDIDATE)
            admitted = client.probe()
            require_candidate(admitted,digest)
            report['admission'] = {k:admitted[k] for k in ['gpu','models','memory']}
            print('Candidate admitted with measured GPU residency/headroom.',flush=True)
            def request(payload):
                if payload.get('model') != CANDIDATE or payload.get('options',{}).get('num_ctx') != CONTEXT:
                    raise ValueError('Candidate model/context changed')
                require_candidate(client.probe(),digest)
                return remote_api('/api/chat',payload)
            yield request
        finally:
            try:
                load(CANDIDATE,0)
                load(BASELINE)
                client.require_ready(client.probe())
                report['restored'] = True
                print('Barbara baseline restored and readiness verified.',flush=True)
            finally:
                report['ended'] = time.time()
                REPORT_PATH.write_text(json.dumps(report))


if __name__ == '__main__':
    with candidate_session() as request:
        trial(model=CANDIDATE, max_turns=24, request=request)
