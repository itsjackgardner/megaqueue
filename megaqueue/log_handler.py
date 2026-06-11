"""Custom logging handler: persists INFO+ to SQLite and fans out to SSE clients."""

import json
import logging
import threading
from datetime import datetime
from queue import SimpleQueue

from megaqueue.models import LogEntry, db_session


class DBLogHandler(logging.Handler):
    """Writes INFO+ log records to the log_entries table and pushes to SSE clients."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self._clients = set()
        self._lock = threading.Lock()

    def _short_module(self, name):
        if name.startswith("megaqueue."):
            return name[len("megaqueue."):]
        return name

    def emit(self, record):
        if record.levelno < logging.INFO:
            return
        module = self._short_module(record.name)
        message = self.format(record)
        now = datetime.utcnow()

        try:
            entry = LogEntry(
                timestamp=now,
                level=record.levelname,
                module=module,
                message=message,
            )
            db_session.add(entry)
            db_session.commit()
        except Exception:
            db_session.rollback()

        event = json.dumps({
            "timestamp": now.isoformat(),
            "level": record.levelname,
            "module": module,
            "message": message,
        })

        with self._lock:
            dead = []
            for q in self._clients:
                try:
                    q.put_nowait(event)
                except Exception:
                    dead.append(q)
            for q in dead:
                self._clients.discard(q)

    def subscribe(self):
        q = SimpleQueue()
        with self._lock:
            self._clients.add(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._clients.discard(q)


log_handler = DBLogHandler()
log_handler.setFormatter(logging.Formatter("%(message)s"))
