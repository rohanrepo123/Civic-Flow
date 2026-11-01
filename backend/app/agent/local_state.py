"""SQLite persistence for the single-process, container-free local runtime."""

import asyncio
import json
import sqlite3
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from backend.app.agent.workflow_serializer import WorkflowSerializer


class LocalCheckpointSaver(SqliteSaver):
    """Use the supported SQLite saver from the graph's async interface."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(sqlite3.connect(path, check_same_thread=False), serde=WorkflowSerializer())

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        rows = await asyncio.to_thread(lambda: list(self.list(config, filter=filter, before=before, limit=limit)))
        for row in rows:
            yield row

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        await asyncio.to_thread(self.delete_thread, thread_id)

    def close(self) -> None:
        self.conn.close()


class StateMap(MutableMapping[str, Any]):
    """Small JSON metadata records; no pickle and no state in logs."""

    def __init__(self, path: Path, namespace: str) -> None:
        self.path = path
        self.namespace = namespace
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS runtime_state (namespace TEXT, key TEXT, value TEXT, PRIMARY KEY(namespace, key))")

    def __getitem__(self, key: str) -> Any:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute("SELECT value FROM runtime_state WHERE namespace=? AND key=?", (self.namespace, key)).fetchone()
        if row is None:
            raise KeyError(key)
        return json.loads(row[0])

    def __setitem__(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT OR REPLACE INTO runtime_state VALUES (?, ?, ?)", (self.namespace, key, encoded))

    def __delitem__(self, key: str) -> None:
        with sqlite3.connect(self.path) as conn:
            cursor = conn.execute("DELETE FROM runtime_state WHERE namespace=? AND key=?", (self.namespace, key))
        if cursor.rowcount == 0:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("SELECT key FROM runtime_state WHERE namespace=?", (self.namespace,)).fetchall()
        return iter(row[0] for row in rows)

    def __len__(self) -> int:
        with sqlite3.connect(self.path) as conn:
            return conn.execute("SELECT count(*) FROM runtime_state WHERE namespace=?", (self.namespace,)).fetchone()[0]
