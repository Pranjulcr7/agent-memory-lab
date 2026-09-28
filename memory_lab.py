"""A small, local teaching example. This is not a Mem0 implementation."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ContextItem:
    layer: str
    source_id: str
    text: str


class MemoryStore:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS facts (
                user_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                text TEXT NOT NULL,
                PRIMARY KEY (user_id, memory_id)
            );
            CREATE TABLE IF NOT EXISTS summaries (
                user_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                text TEXT NOT NULL,
                PRIMARY KEY (user_id, source_id)
            );
            """
        )

    def remember(self, user_id: str, memory_id: str, text: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO facts VALUES (?, ?, ?)",
                (user_id, memory_id, text),
            )
            self.db.execute(
                "INSERT OR REPLACE INTO summaries VALUES (?, ?, ?)",
                (user_id, memory_id, "Saved profile summary: " + text),
            )

    def delete_record_only(self, user_id: str, memory_id: str) -> None:
        """Intentionally incomplete: the separately stored summary survives."""
        with self.db:
            self.db.execute(
                "DELETE FROM facts WHERE user_id = ? AND memory_id = ?",
                (user_id, memory_id),
            )

    def delete_record_and_summary(self, user_id: str, memory_id: str) -> None:
        """Remove the source and its one known derived copy in this toy schema."""
        with self.db:
            self.db.execute(
                "DELETE FROM summaries WHERE user_id = ? AND source_id = ?",
                (user_id, memory_id),
            )
            self.db.execute(
                "DELETE FROM facts WHERE user_id = ? AND memory_id = ?",
                (user_id, memory_id),
            )

    def read_context(self, user_id: str) -> list[ContextItem]:
        facts = self.db.execute(
            "SELECT memory_id, text FROM facts WHERE user_id = ? ORDER BY memory_id",
            (user_id,),
        ).fetchall()
        summaries = self.db.execute(
            "SELECT source_id, text FROM summaries WHERE user_id = ? ORDER BY source_id",
            (user_id,),
        ).fetchall()
        return [ContextItem("facts", key, text) for key, text in facts] + [
            ContextItem("summaries", key, text) for key, text in summaries
        ]

    def counts(self, user_id: str) -> dict[str, int]:
        return {
            table: self.db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            for table in ("facts", "summaries")
        }

    def close(self) -> None:
        self.db.close()


class AgentSession:
    def __init__(self, store: MemoryStore, user_id: str):
        self.context = store.read_context(user_id)

    def make_prompt(self, question: str) -> str:
        notes = "\n".join(item.text for item in self.context) or "No saved facts."
        return f"Saved context:\n{notes}\n\nUser question:\n{question}"


def check_context(
    session: AgentSession, marker: str, *, baseline_seen: bool
) -> dict:
    if not marker or not baseline_seen:
        return {
            "status": "INCONCLUSIVE",
            "reason": "A non-empty marker must have been observed before deletion.",
            "hits": [],
        }
    hits = [
        {"layer": item.layer, "source_id": item.source_id}
        for item in session.context
        if marker in item.text
    ]
    return {
        "status": "FAIL" if hits else "PASS",
        "reason": "Marker is present in context." if hits else "Marker is absent from this context.",
        "hits": hits,
        "coverage": "Exact marker in the context built from facts and summaries only.",
    }
