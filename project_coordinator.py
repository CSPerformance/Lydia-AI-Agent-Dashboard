"""Lydia v157 durable project coordinator.

One user objective -> one durable project -> many amendments/work items.
This module owns coordination state only. It does not execute infrastructure.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

TERMINAL = {"complete", "cancelled", "blocked"}
ACTIVE = {"active", "recovering", "waiting"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    operation_id TEXT,
    created REAL NOT NULL,
    updated REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS amendments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created REAL NOT NULL,
    applied INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS work_items (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    worker_id TEXT,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    strategy TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    parent_id TEXT,
    evidence TEXT NOT NULL DEFAULT '{}',
    created REAL NOT NULL,
    updated REAL NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_projects_owner_status
ON projects(owner,status);

CREATE INDEX IF NOT EXISTS idx_work_project_status
ON work_items(project_id,status);
"""


class ProjectCoordinator:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "projects.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript(_SCHEMA)
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def create_project(self, owner, objective, operation_id=None):
        owner = str(owner).strip()
        objective = str(objective).strip()
        if not owner or not objective:
            raise ValueError("Project requires owner and objective")
        project_id = "project-" + uuid.uuid4().hex[:16]
        now = time.time()
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
                (project_id, owner, objective, "active",
                 operation_id, now, now),
            )
        return project_id

    def get(self, project_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,owner,objective,status,operation_id,created,updated "
                "FROM projects WHERE id=?",
                (project_id,),
            ).fetchone()
        if not row:
            return None
        keys = ("id","owner","objective","status","operation_id","created","updated")
        return dict(zip(keys,row))

    def active_project(self, owner):
        with self.connect() as db:
            row = db.execute(
                "SELECT id FROM projects "
                "WHERE owner=? AND status IN ('active','recovering','waiting') "
                "ORDER BY updated DESC LIMIT 1",
                (owner,),
            ).fetchone()
        return self.get(row[0]) if row else None

    def amend(self, project_id, owner, text):
        text = str(text).strip()
        project = self.get(project_id)
        if not project or project["owner"] != owner:
            raise ValueError("Project ownership mismatch")
        if project["status"] not in ACTIVE:
            raise ValueError("Cannot amend terminal project")
        if not text:
            raise ValueError("Empty amendment")
        amendment_id = "amend-" + uuid.uuid4().hex[:16]
        now = time.time()
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO amendments(id,project_id,text,created,applied) "
                "VALUES (?,?,?,?,0)",
                (amendment_id,project_id,text,now),
            )
            db.execute(
                "UPDATE projects SET updated=? WHERE id=?",
                (now,project_id),
            )
        return amendment_id

    def amendments(self, project_id, unapplied_only=False):
        sql = ("SELECT id,text,created,applied FROM amendments "
               "WHERE project_id=?")
        if unapplied_only:
            sql += " AND applied=0"
        sql += " ORDER BY created,id"
        with self.connect() as db:
            rows = db.execute(sql,(project_id,)).fetchall()
        return [
            {"id":r[0],"text":r[1],"created":r[2],"applied":bool(r[3])}
            for r in rows
        ]

    def mark_amendments_applied(self, project_id, amendment_ids):
        ids = list(dict.fromkeys(amendment_ids))
        if not ids:
            return
        with self.lock, self.connect() as db:
            for amendment_id in ids:
                db.execute(
                    "UPDATE amendments SET applied=1 "
                    "WHERE id=? AND project_id=?",
                    (amendment_id,project_id),
                )
            db.execute(
                "UPDATE projects SET updated=? WHERE id=?",
                (time.time(),project_id),
            )

    def similar_work_exists(self, project_id, worker_id, objective, strategy=None):
        """Conservative exact-normalized duplicate guard for project scheduling."""
        import re

        def norm(value):
            value = str(value or "").lower()
            value = re.sub(r"[^a-z0-9]+", " ", value)
            return " ".join(value.split())

        wanted_objective = norm(objective)
        wanted_strategy = norm(strategy)

        for item in self.work_items(project_id):
            if item.get("worker_id") != worker_id:
                continue

            if item.get("status") in {"cancelled"}:
                continue

            existing_objective = norm(item.get("objective"))
            existing_strategy = norm(item.get("strategy"))

            if wanted_objective and wanted_objective == existing_objective:
                return item

            if (
                wanted_strategy
                and wanted_strategy == existing_strategy
                and item.get("status") in {
                    "queued", "dispatching", "running", "complete"
                }
            ):
                return item

        return None

    def add_work_unique(self, project_id, objective, worker_id=None,
                        strategy=None, parent_id=None):
        duplicate = self.similar_work_exists(
            project_id, worker_id, objective, strategy
        )
        if duplicate:
            return {
                "created": False,
                "work_id": duplicate["id"],
                "duplicate_status": duplicate["status"],
            }

        work_id = self.add_work(
            project_id,
            objective,
            worker_id=worker_id,
            strategy=strategy,
            parent_id=parent_id,
        )
        return {
            "created": True,
            "work_id": work_id,
            "duplicate_status": None,
        }

    def add_work(self, project_id, objective, worker_id=None,
                 strategy=None, parent_id=None):
        if not self.get(project_id):
            raise ValueError("Unknown project")
        objective = str(objective).strip()
        if not objective:
            raise ValueError("Work item requires objective")
        if worker_id not in {None,"lydia","adam","barbara","otho"}:
            raise ValueError("Unknown worker")
        work_id = "work-" + uuid.uuid4().hex[:16]
        now = time.time()
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO work_items "
                "(id,project_id,worker_id,objective,status,strategy,"
                "attempt,parent_id,evidence,created,updated) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (work_id,project_id,worker_id,objective,"queued",
                 strategy,0,parent_id,"{}",now,now),
            )
            db.execute(
                "UPDATE projects SET updated=? WHERE id=?",
                (now,project_id),
            )
        return work_id

    def claim(self, work_id, worker_id):
        if worker_id not in {"lydia","adam","barbara","otho"}:
            raise ValueError("Unknown worker")
        now = time.time()
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT status,worker_id,attempt FROM work_items WHERE id=?",
                (work_id,),
            ).fetchone()
            if not row:
                raise ValueError("Unknown work item")
            status, assigned, attempt = row
            if status != "queued":
                return False
            if assigned not in (None,worker_id):
                return False
            cur = db.execute(
                "UPDATE work_items SET worker_id=?,status='dispatching',"
                "attempt=?,updated=? WHERE id=? AND status='queued'",
                (worker_id,attempt+1,now,work_id),
            )
            return cur.rowcount == 1

    def update_running_evidence(self, work_id, evidence):
        """Persist remote execution identity while work is still running."""
        item = self.work_item(work_id)
        if not item:
            raise ValueError("Unknown work item")
        if item["status"] not in {"dispatching", "running"}:
            raise ValueError("In-flight evidence requires dispatching or running work")

        current = dict(item.get("evidence") or {})
        current.update(dict(evidence or {}))

        with self.lock, self.connect() as db:
            now = time.time()
            db.execute(
                "UPDATE work_items SET status='running',evidence=?,updated=? "
                "WHERE id=? AND status IN ('dispatching','running')",
                (json.dumps(current, ensure_ascii=False), now, work_id),
            )
            db.execute(
                "UPDATE projects SET updated=? WHERE id=?",
                (now, item["project_id"]),
            )

    def finish_work(self, work_id, status, evidence=None):
        if status not in {"complete","failed","blocked","cancelled","interrupted"}:
            raise ValueError("Invalid work status")
        payload = json.dumps(evidence or {}, ensure_ascii=False)
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT project_id FROM work_items WHERE id=?",
                (work_id,),
            ).fetchone()
            if not row:
                raise ValueError("Unknown work item")
            now = time.time()
            db.execute(
                "UPDATE work_items SET status=?,evidence=?,updated=? WHERE id=?",
                (status,payload,now,work_id),
            )
            db.execute(
                "UPDATE projects SET updated=? WHERE id=?",
                (now,row[0]),
            )

    def work_items(self, project_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,worker_id,objective,status,strategy,attempt,"
                "parent_id,evidence,created,updated "
                "FROM work_items WHERE project_id=? ORDER BY created,id",
                (project_id,),
            ).fetchall()
        keys = ("id","worker_id","objective","status","strategy","attempt",
                "parent_id","evidence","created","updated")
        result = []
        for row in rows:
            item = dict(zip(keys,row))
            try:
                item["evidence"] = json.loads(item["evidence"])
            except (TypeError,ValueError):
                item["evidence"] = {}
            result.append(item)
        return result

    def work_item(self, work_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT id,project_id,worker_id,objective,status,strategy,"
                "attempt,parent_id,evidence,created,updated "
                "FROM work_items WHERE id=?",
                (work_id,),
            ).fetchone()
        if not row:
            return None
        keys = ("id","project_id","worker_id","objective","status","strategy",
                "attempt","parent_id","evidence","created","updated")
        item = dict(zip(keys,row))
        try:
            item["evidence"] = json.loads(item["evidence"])
        except (TypeError,ValueError):
            item["evidence"] = {}
        return item

    def queued_work(self, project_id, worker_id=None):
        sql = (
            "SELECT id FROM work_items WHERE project_id=? AND status='queued'"
        )
        args = [project_id]
        if worker_id is not None:
            sql += " AND (worker_id=? OR worker_id IS NULL)"
            args.append(worker_id)
        sql += " ORDER BY created,id"
        with self.connect() as db:
            rows = db.execute(sql, tuple(args)).fetchall()
        return [self.work_item(row[0]) for row in rows]

    def running_work(self, project_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id FROM work_items WHERE project_id=? AND status IN ('dispatching','running') "
                "ORDER BY created,id",
                (project_id,),
            ).fetchall()
        return [self.work_item(row[0]) for row in rows]

    def requeue_failed(self, work_id, objective, strategy):
        """Create a narrower successor while preserving failed evidence/history."""
        previous = self.work_item(work_id)
        if not previous:
            raise ValueError("Unknown work item")
        if previous["status"] not in {"failed", "blocked", "interrupted"}:
            raise ValueError("Only failed, blocked or interrupted work may be recovered")

        strategy = str(strategy or "").strip()
        objective = str(objective or "").strip()

        if not strategy or not objective:
            raise ValueError("Recovery requires a changed strategy and objective")

        if strategy == str(previous.get("strategy") or "").strip():
            raise ValueError("Recovery must materially change strategy")

        return self.add_work(
            previous["project_id"],
            objective,
            worker_id=previous["worker_id"],
            strategy=strategy,
            parent_id=previous["id"],
        )

    def interrupt_orphaned(self, work_id, reason):
        """Preserve a running item whose controller/remote identity was lost."""
        item = self.work_item(work_id)
        if not item:
            raise ValueError("Unknown work item")
        if item["status"] not in {"dispatching", "running"}:
            return False

        evidence = dict(item.get("evidence") or {})
        evidence.update({
            "interrupted": True,
            "reason": str(reason),
            "safe_to_redispatch": False,
        })

        self.finish_work(work_id, "interrupted", evidence)
        return True

    def orphaned_running_work(self, project_id):
        """Running work with no durable remote handle cannot be assumed alive."""
        orphaned = []
        now = time.time()
        for item in self.running_work(project_id):
            evidence = item.get("evidence") or {}
            if evidence.get("remote_identity"):
                continue
            if item["status"] == "dispatching" and now - item["updated"] < 60:
                continue
            orphaned.append(item)
        return orphaned

    def failure_kind(self, work_id):
        item = self.work_item(work_id)
        if not item:
            raise ValueError("Unknown work item")

        evidence = item.get("evidence") or {}
        text = json.dumps(evidence, ensure_ascii=False).lower()

        if "action budget exhausted" in text:
            return "action_budget"
        if "timeout" in text or "timed out" in text:
            return "timeout"
        if "unavailable" in text or "connection" in text:
            return "availability"
        return "other"

    def bind_operation(self, project_id, operation_id):
        with self.lock, self.connect() as db:
            db.execute(
                "UPDATE projects SET operation_id=?,updated=? WHERE id=?",
                (operation_id,time.time(),project_id),
            )

    def set_status(self, project_id, status):
        if status not in ACTIVE | TERMINAL:
            raise ValueError("Invalid project status")
        with self.lock, self.connect() as db:
            db.execute(
                "UPDATE projects SET status=?,updated=? WHERE id=?",
                (status,time.time(),project_id),
            )


# ---------------------------------------------------------------------------
# Continuation / amendment classification
# ---------------------------------------------------------------------------

_CONTINUATION_PATTERNS = (
    r"^\s*(?:please\s+)?(?:continue|keep going|keep working|resume|proceed)\b",
    r"^\s*(?:please\s+)?(?:don'?t|do not)\s+stop\b",
    r"^\s*(?:also|and)\s+(?:add|include|use|have|make|give|let|keep)\b",
    r"^\s*(?:use|have|ask|tell)\s+(?:adam|barbara|both|the team)\b",
    r"^\s*(?:make|give|let)\s+otho\b",
    r"^\s*otho\s+(?:should|needs?|must|can|also)\b",
    r"^\s*(?:this|that|it)\s+(?:should|needs?|must|also|still)\b",
)

_NEW_PROJECT_PATTERNS = (
    r"^\s*(?:new|different|separate)\s+(?:project|task|job)\b",
    r"^\s*(?:start|create|begin)\s+(?:a\s+)?(?:new|different|separate)\b",
)


def continuation_intent(text, active_project=None):
    """Return deterministic routing intent: amendment, new, or undecided.

    Only obvious follow-ups are auto-attached. Ambiguous substantive requests
    remain undecided so the caller can use normal routing instead of silently
    hijacking unrelated conversation.
    """
    import re

    clean = str(text or "").strip()
    if not clean:
        return "undecided"

    for pattern in _NEW_PROJECT_PATTERNS:
        if re.search(pattern, clean, re.I):
            return "new"

    if active_project:
        project_id = str(active_project.get("id") or "")
        operation_id = str(active_project.get("operation_id") or "")

        if project_id and re.search(r"\b" + re.escape(project_id) + r"\b", clean, re.I):
            return "amendment"

        if operation_id and re.search(r"\b" + re.escape(operation_id) + r"\b", clean, re.I):
            return "amendment"

        for pattern in _CONTINUATION_PATTERNS:
            if re.search(pattern, clean, re.I):
                return "amendment"

    return "undecided"
