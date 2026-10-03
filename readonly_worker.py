"""Controller-mediated observation tools for read-only Adam/Barbara assignments."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat

from agent_support import ToolAgent, STRING, save_record, tool

# No shell/model code runs on the target. Inputs are validated before serialization.
NETWORK_PROBE = '''import concurrent.futures,json,socket,ssl,sys
request=json.loads(sys.argv[1]);host=request['host']
def probe(port):
 row={'port':port,'tcp':'closed_or_filtered'}
 try:
  with socket.create_connection((host,port),timeout=1.5) as s:
   row['tcp']='open';s.settimeout(2)
   if port in (443,8443):
    s=ssl._create_unverified_context().wrap_socket(s,server_hostname=host)
    row['tls']=True
   protocol='RTSP' if port in (554,8554) else 'HTTP'
   request=(f'OPTIONS rtsp://{host}:{port}/ RTSP/1.0\\r\\nCSeq: 1\\r\\n\\r\\n' if protocol=='RTSP' else f'HEAD / HTTP/1.0\\r\\nHost: {host}\\r\\n\\r\\n')
   s.sendall(request.encode());row['response']=s.recv(2048).decode('utf-8','replace')
 except Exception as e:row['observation_error']=type(e).__name__
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 rows=list(pool.map(probe,request['ports']))
print(json.dumps({'host':host,'ports':rows,'scope':'TCP and HTTP/RTSP greeting only; negative results do not exclude other protocols or ports'}))
'''


def dispatch_readonly(worker, work_order, owner, stop, root, execute, research, on_dispatch=None, request=None):
    order = json.loads(work_order)
    contract = order['original_goal']
    if worker not in {'adam', 'barbara'} or contract.get('read_only') is not True or order.get('owner') != owner:
        raise ValueError('Read-only dispatch requires matching owner and original contract')
    check = order['step']['check']
    if not isinstance(check, dict) or check.get('kind') != 'json_file' or check.get('path') != 'report.json':
        raise ValueError('Read-only workers produce a bound report.json; use a json_file check')
    agent = ToolAgent(Path(root) / 'calls', owner, stop, request=request, worker=worker, max_turns=10)
    identity = agent.id
    if on_dispatch:
        on_dispatch(identity)
    target = 'vm202' if worker == 'adam' else 'powermox'
    hosts = set(re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)', contract['objective']))
    observations = []
    def observe(command, kind, host=None):
        if stop.is_set():
            raise InterruptedError('Observation cancelled')
        output = execute(target, command)
        from operator_runtime import successful, output_body
        row = {'target': target, 'kind': kind, 'host': host, 'command_sha256': hashlib.sha256(command.encode()).hexdigest(),
               'success': successful(output), 'output': output_body(output)[:14000]}
        observations.append(row)
        return row
    def network_probe(host, ports):
        address = ipaddress.ip_address(host)
        if host not in hosts or address.version != 4 or address.is_multicast or address.is_unspecified:
            raise ValueError('Probe host must be an explicit IPv4 target in the original objective')
        if not isinstance(ports, list) or not 1 <= len(ports) <= 32 or any(type(p) is not int or not 1 <= p <= 65535 for p in ports):
            raise ValueError('Choose 1–32 TCP ports in 1–65535')
        return observe('python3 -c ' + shlex.quote(NETWORK_PROBE) + ' ' + shlex.quote(json.dumps({'host': host, 'ports': sorted(set(ports))})), 'network_probe', host)
    def host_facts():
        program = ("import json,socket,platform; "
                   "m=dict(line.split(':',1) for line in open('/proc/meminfo')); "
                   "print(json.dumps({'hostname':socket.gethostname(),'kernel':platform.release(),"
                   "'memory_total_bytes':int(m['MemTotal'].split()[0])*1024,"
                   "'memory_available_bytes':int(m['MemAvailable'].split()[0])*1024}))")
        return observe('python3 -c ' + shlex.quote(program), 'host_facts')
    def finish(summary, limitations):
        if not any(row['success'] for row in observations):
            raise ValueError('Use observation tools successfully before reporting; prose is not evidence')
        missing = hosts - {row['host'] for row in observations if row['kind'] == 'network_probe' and row['success']}
        if missing:
            raise ValueError('Observe the original target IPs before reporting: ' + ', '.join(sorted(missing)))
        if not isinstance(summary, str) or not isinstance(limitations, str) or not limitations.strip():
            raise ValueError('Report actual observations and explicit coverage limitations')
        return {'summary': summary, 'limitations': limitations}
    tools = [tool('network_probe', 'Observe TCP connections and bounded HTTP/RTSP greetings on the explicit goal IP. No changes, login or downloads.',
                  {'host': STRING, 'ports': {'type': 'array', 'items': {'type': 'integer'}, 'maxItems': 32}}),
             tool('host_facts', 'Read hostname, OS and available memory on the assigned host.', {}),
             tool('research', 'Research relevant public documentation using the existing web broker.', {'query': STRING}),
             tool('finish', 'Return a summary grounded in tool observations and explicit limitations. This does not claim full goal verification.',
                  {'summary': STRING, 'limitations': STRING})]
    result = agent.run('You are '+worker.capitalize()+', performing a read-only investigation for Lydia. '
        'Use tools, inspect their errors, and consult documentation when protocol interpretation requires it. '
        'No configuration changes or arbitrary execution are available. A closed port or missing greeting does not prove no local video interface exists.',
        order, tools, {'network_probe': network_probe, 'host_facts': host_facts,
                       'research': lambda query: research({'query': query})[:14000], 'finish': finish})
    report = {'worker_id': worker, 'owner': owner, 'goal_sha256': hashlib.sha256(work_order.encode()).hexdigest(),
              'observations': observations, **result, 'coverage': 'bounded observations, not exhaustive protocol discovery'}
    path = Path(root) / 'observations' / (identity + '.json')
    save_record(path, report)
    return {'worker_id': worker, 'owner': owner, 'goal_sha256': report['goal_sha256'],
            'job_id': identity, 'remote_run_id': identity, 'workspace': None,
            'status': 'executed_unverified', 'mode': 'controller_readonly',
            'report_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'independently_verified': False, 'backend': 'local model with controller observation tools'}


def verify_readonly(binding, check, root):
    identity = binding.get('job_id', '')
    if not re.fullmatch(r'support-[a-f0-9]{32}', identity) or check.get('kind') != 'json_file' or check.get('path') != 'report.json':
        raise ValueError('Invalid bound observation artifact')
    path = Path(root) / 'observations' / (identity + '.json')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1048576:
            raise ValueError('Invalid observation report file')
        raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('Observation report exceeds size limit')
    if hashlib.sha256(raw).hexdigest() != binding.get('report_sha256'):
        raise ValueError('Observation report changed after dispatch')
    data = json.loads(raw)
    if any(data.get(k) != binding.get(k) for k in ('worker_id', 'owner', 'goal_sha256')) or not any(r.get('success') for r in data.get('observations', [])):
        raise ValueError('Observation report lacks matching identity or successful tool evidence')
    return 'EXIT_CODE=0\nSTDOUT:\n' + raw.decode()


def summarize_report(report):
    """Render measured fields directly; do not substitute a planner's stale values."""
    lines = []
    for observation in report.get('observations', []):
        if not isinstance(observation, dict):
            continue
        if not observation.get('success'):
            continue
        try:
            facts = json.loads(observation['output'])
        except (ValueError, KeyError, TypeError):
            continue
        if observation.get('kind') == 'host_facts' and isinstance(facts, dict):
            available = facts.get('memory_available_bytes')
            total = facts.get('memory_total_bytes')
            lines.append(f"{report['worker_id'].capitalize()} observed hostname: {facts.get('hostname', 'unknown')}.")
            if type(available) is int and type(total) is int:
                lines.append(f'Available memory: {available / 1024**3:.2f} GiB ({available} bytes); total: {total / 1024**3:.2f} GiB.')
        elif observation.get('kind') == 'network_probe' and isinstance(facts, dict):
            opened = [str(p['port']) for p in facts.get('ports', []) if p.get('tcp') == 'open']
            lines.append(f"{report['worker_id'].capitalize()} probed {facts.get('host')}: open TCP ports: {', '.join(opened) or 'none observed among selected ports'}.")
            for port in facts.get('ports', []):
                if port.get('response'):
                    lines.append(f"Port {port['port']}: {port['response'].splitlines()[0][:160]}")
            lines.append('Coverage: selected TCP ports and HTTP/RTSP greetings only. This does not rule out other ports or establish ONVIF/WebRTC support.')
    return '\n'.join(lines) or 'Worker observation evidence was checked; see the bound report for coverage and limitations.'
