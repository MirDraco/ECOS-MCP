import hashlib
import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any


class Cache:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = Lock()
        with self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires REAL NOT NULL)")

    @staticmethod
    def key(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()
        return hashlib.sha256(raw).hexdigest()

    def get(self, key: str) -> Any | None:
        with self.lock:
            row = self.db.execute("SELECT value, expires FROM cache WHERE key=?", (key,)).fetchone()
            if not row:
                return None
            if row[1] <= time.time():
                self.db.execute("DELETE FROM cache WHERE key=?", (key,))
                self.db.commit()
                return None
            return json.loads(row[0])

    def set(self, key: str, value: Any, ttl: int) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, json.dumps(value, ensure_ascii=True), time.time() + ttl))
