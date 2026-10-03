"""Durable portal feedback. Reports are untrusted data, never tool instructions."""
import json
import re
import sqlite3
import time
import uuid


def redact(text):
    text = re.sub(r'(?i)(authorization|cookie|password|secret|api[_-]?key|(?:access[_-]?)?token)\s*[:=]\s*[^\n]+', '[REDACTED SECRET FIELD]', text)
    text = re.sub(r'\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{12,}|\beyJ[\w-]+\.[\w-]+\.[\w-]+', '[REDACTED]', text)
    return re.sub(r'(https?://[^\s?#]+)[?#][^\s]*', r'\1?[REDACTED]', text)


class Reports:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = root/'reports.sqlite3'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, owner TEXT, request_id TEXT, created REAL, status TEXT, body TEXT, UNIQUE(owner,request_id))')
        self.path.chmod(0o600)

    def submit(self, owner, payload):
        if not isinstance(payload, dict):
            raise ValueError('Invalid report')
        request_id = payload.get('request_id', '')
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', request_id):
            raise ValueError('Invalid submission reference')
        body = {}
        for key, limit in [('summary',160),('steps',3000),('expected',2000),('actual',3000),('diagnostics',12000)]:
            value = payload.get(key, '')
            if not isinstance(value, str) or len(value) > limit or (key in {'summary','actual'} and not value.strip()):
                raise ValueError('Please provide a short title and describe what went wrong; shorten any oversized fields.')
            body[key] = redact(value.strip())
        encoded = json.dumps(body, sort_keys=True)
        with sqlite3.connect(self.path, timeout=10) as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT id,status,body FROM reports WHERE owner=? AND request_id=?', (owner,request_id)).fetchone()
            if previous:
                if previous[2] != encoded:
                    raise ValueError('Submission reference already used; start a new report')
                return {'id':previous[0], 'status':previous[1]}
            if db.execute('SELECT count(*) FROM reports WHERE owner=? AND created>?', (owner,time.time()-3600)).fetchone()[0] >= 20:
                raise ValueError('Report limit reached. Please keep your notes and try again later.')
            identity = 'BUG-'+uuid.uuid4().hex[:12].upper()
            db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?)', (identity,owner,request_id,time.time(),'open',encoded))
        return {'id':identity, 'status':'open'}

    def list(self, owner, admin=False):
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT id,owner,created,status,body FROM reports '+
                              ('' if admin else 'WHERE owner=? ')+
                              'ORDER BY created DESC LIMIT 100', () if admin else (owner,)).fetchall()
        return [{'id':r[0],'owner':r[1],'created':r[2],'status':r[3],**json.loads(r[4])} for r in rows]
