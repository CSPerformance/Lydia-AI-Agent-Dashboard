"""Durable, owner-scoped team learning on Lydia's data NVMe.

Store complete bounded evidence records, retrieve small relevant excerpts. Only
controller-verified outcomes become reusable procedures. Failed work is retained
for diagnosis, never promoted by model prose. Memory is reference, not authority.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

from agent_support import diagnostic


class TeamMemory:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'knowledge.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS experiences (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
                    outcome TEXT NOT NULL, title TEXT NOT NULL, procedure TEXT NOT NULL,
                    evidence TEXT NOT NULL, recorded REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS experience_owner ON experiences(owner, outcome);
                CREATE VIRTUAL TABLE IF NOT EXISTS experience_search USING fts5(
                    id UNINDEXED, title, procedure);
            ''')
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    def _record(self, owner, scope, title, procedure, evidence, outcome):
        if not all(isinstance(v, str) and v.strip() for v in (owner, scope, title, procedure)):
            raise ValueError('Memory requires owner, scope, title and procedure')
        public = diagnostic({'title': title, 'procedure': procedure, 'evidence': evidence})
        encoded = json.dumps(public['evidence'], sort_keys=True)
        if len(encoded) > 250000:
            raise ValueError('Evidence record too large; retain an artifact receipt instead')
        identity = hashlib.sha256((owner + '\0' + scope + '\0' + title + '\0' + encoded).encode()).hexdigest()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO experiences VALUES (?,?,?,?,?,?,?,?)',
                (identity, owner, scope, outcome, public['title'], public['procedure'], encoded, time.time()))
            db.execute('DELETE FROM experience_search WHERE id=?', (identity,))
            db.execute('INSERT INTO experience_search VALUES (?,?,?)',
                       (identity, public['title'], public['procedure']))
        return identity

    def record_operation(self, operation):
        """Promote only controller-complete operations with current proof for all steps."""
        state = operation.state
        plan = state.get('plan', [])
        complete = (operation.status == 'complete' and bool(plan)
            and all(step['id'] in state.get('verified', {}) for step in plan)
            and not state.get('inflight') and not state.get('unresolved_execution')
            and not (set(operation.contract.get('completion_requirements', [])) - set(state.get('acceptance', {})))
            and (not operation.contract.get('register_required') or bool(state.get('registered'))))
        with operation.store.connect() as db:
            rows = db.execute('SELECT id,phase,success,command_hash,output_hash FROM receipts WHERE operation=?',
                              (operation.id,)).fetchall()
        receipts = {row[0]: {'phase':row[1], 'success':bool(row[2]), 'command_hash':row[3], 'output_hash':row[4]} for row in rows}
        complete = complete and all(receipts.get(r, {}).get('success') and receipts[r]['phase'] == 'verify'
                                    for r in state.get('verified', {}).values())
        return self._record(operation.owner, 'team', operation.contract['objective'],
            json.dumps({'decisions': state.get('decisions'), 'outcomes': plan,
                        'report': state.get('report'), 'failures': state.get('failures', []),
                        'boundary': 'Reinspect live state and revalidate checks; past success is not current authorization.'}),
            {'operation_id':operation.id, 'status':operation.status, 'receipts':receipts,
             'acceptance':state.get('acceptance', {}), 'reason':state.get('reason')},
            'verified' if complete else 'unfinished')

    def record_acceptance(self, owner, title, procedure, checks, source_hashes):
        """Controller commissioning API, deliberately not exposed as a model tool."""
        if (not isinstance(checks, list) or not checks
                or any(c.get('passed') is not True or not re.fullmatch(r'[a-f0-9]{64}', c.get('receipt_sha256','')) for c in checks)
                or not source_hashes or any(not re.fullmatch(r'[a-f0-9]{64}', value) for value in source_hashes.values())):
            raise ValueError('Passing controller checks and source hashes are required')
        return self._record(owner, 'team', title, procedure,
                            {'checks':checks, 'source_hashes':source_hashes}, 'verified')

    def retrieve(self, owner, query, *, limit=5, budget=7000):
        terms = list(dict.fromkeys(re.findall(r'[a-z0-9_]{3,}', str(query).lower())))[:40]
        terms = [t for t in terms if t not in {'the','and','for','this','that','you','please','with','from','have'}]
        if not terms:
            return []
        expression = ' OR '.join('"' + t + '"' for t in terms)
        with self.connect() as db:
            rows = db.execute('''SELECT e.id,e.title,e.procedure,e.recorded FROM experience_search s
                JOIN experiences e ON e.id=s.id WHERE experience_search MATCH ?
                AND e.owner=? AND e.outcome='verified' ORDER BY bm25(experience_search),e.recorded DESC LIMIT ?''',
                (expression, owner, max(1, min(limit, 10)))).fetchall()
        result = []
        for identity, title, procedure, recorded in rows:
            row = {'id':identity, 'title':title[:500], 'procedure':procedure[:2000],
                   'recorded':recorded, 'provenance':'controller_verified_reference'}
            length = len(json.dumps(row))
            if length > budget:
                break
            result.append(row)
            budget -= length
        return result


def reference(root, owner, query, *, budget=7000):
    """Optional retrieval never blocks the task or creates an absent database."""
    path = Path(root) / 'knowledge.sqlite3'
    if not path.is_file():
        return []
    try:
        return TeamMemory(root).retrieve(owner, query, budget=budget)
    except (OSError, sqlite3.Error, ValueError):
        return []
