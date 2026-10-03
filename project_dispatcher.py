"""Lydia v157 parallel project dispatcher."""

import threading
import time


class ParallelProjectDispatcher:
    """Dispatch independent project work concurrently to available workers."""

    def __init__(self, coordinator, runners):
        self.coordinator = coordinator
        self.runners = dict(runners)
        self._lock = threading.RLock()
        self._threads = {}

    def _run_one(self, project_id, work_id, worker_id):
        try:
            item = self.coordinator.work_item(work_id)
            if not item:
                return

            result = self.runners[worker_id](item)

            if isinstance(result, dict):
                status = result.get("status", "complete")
                evidence = result
            else:
                status = "complete"
                evidence = {"result": result}

            if status not in {"complete", "failed", "blocked", "cancelled"}:
                status = "complete"

            self.coordinator.finish_work(work_id, status, evidence)

        except Exception as exc:
            self.coordinator.finish_work(
                work_id,
                "failed",
                {
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                },
            )
        finally:
            with self._lock:
                self._threads.pop(work_id, None)

    def dispatch_available(self, project_id):
        """Start all safe queued worker-specific work without serial waiting."""
        started = []

        for worker_id in ("adam", "barbara"):
            if worker_id not in self.runners:
                continue

            # One concurrent assignment per worker initially. This prevents
            # duplicate saturation while still allowing Adam + Barbara together.
            if any(
                item["worker_id"] == worker_id
                for item in self.coordinator.running_work(project_id)
            ):
                continue

            queued = self.coordinator.queued_work(project_id, worker_id)
            if not queued:
                continue

            item = queued[0]

            if not self.coordinator.claim(item["id"], worker_id):
                continue

            thread = threading.Thread(
                target=self._run_one,
                args=(project_id, item["id"], worker_id),
                daemon=True,
                name=f"project-{project_id}-{worker_id}-{item['id']}",
            )

            with self._lock:
                self._threads[item["id"]] = thread

            thread.start()
            started.append({
                "work_id": item["id"],
                "worker_id": worker_id,
            })

        return started

    def active(self):
        with self._lock:
            return {
                work_id: thread.name
                for work_id, thread in self._threads.items()
                if thread.is_alive()
            }

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout

        while True:
            with self._lock:
                threads = list(self._threads.values())

            if not threads:
                return True

            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False

            threads[0].join(
                None if remaining is None else min(remaining, 0.1)
            )
