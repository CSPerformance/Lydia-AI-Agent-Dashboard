"""Controller-owned host measurements for read-only planning outcomes."""
import json
import shlex

PROGRAM = '''import json,shutil,socket,sys
metric=sys.argv[1]
if metric=='hostname':
 result={'hostname':socket.gethostname()}
elif metric=='memory':
 rows=dict(line.split(':',1) for line in open('/proc/meminfo'))
 result={key:int(rows[field].split()[0])*1024 for key,field in [('total_bytes','MemTotal'),('available_bytes','MemAvailable')]}
else:
 usage=shutil.disk_usage('/')
 result={'path':'/','total_bytes':usage.total,'used_bytes':usage.used,'available_bytes':usage.free}
print(json.dumps(result))
'''


def command(metric):
    if metric not in {'hostname','memory','disk'}:
        raise ValueError('Choose hostname, memory or disk observation')
    return shlex.join(['python3','-c',PROGRAM,metric])


def valid(metric, value):
    if not isinstance(value, dict):
        return False
    if metric == 'hostname':
        return isinstance(value.get('hostname'), str) and bool(value['hostname'].strip())
    if metric not in {'memory', 'disk'}:
        return False
    total, available = value.get('total_bytes'), value.get('available_bytes')
    if type(total) is not int or type(available) is not int:
        return False
    if total <= 0 or available < 0 or available > total:
        return False
    if metric == 'disk':
        if value.get('path') != '/':
            return False
        used = value.get('used_bytes')
        if type(used) is not int or used < 0 or used > total or used + available > total:
            return False
    return True


def summary(target, metric, value):
    if metric == 'hostname':
        return target + ': hostname ' + value['hostname'] + '.'
    label = 'available memory' if metric == 'memory' else 'free space on /'
    return f"{target}: {label} {value['available_bytes'] / 1024**3:.2f} GiB of {value['total_bytes'] / 1024**3:.2f} GiB."
