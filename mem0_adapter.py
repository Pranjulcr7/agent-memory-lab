"""Real Mem0 storage with explicit, offline model fixtures for integration tests."""

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from math import sqrt
import os
from pathlib import Path
import re
from unittest.mock import patch


VERSIONS = {"mem0ai": "2.1.0", "qdrant-client": "1.19.1"}


class TokenHashEmbeddings:
    """Stable token-count vectors, not learned semantic embeddings."""

    dimensions = 128

    def embed(self, text, memory_action=None):
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[\w-]+", text.lower()):
            digest = sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        norm = sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class DisabledLLM:
    def generate_response(self, *args, **kwargs):
        raise RuntimeError("This offline fixture must not call an LLM. Use infer=False.")


class Mem0Adapter:
    """Single-process test adapter for a dedicated local Qdrant directory."""

    def __init__(self, directory: Path):
        for package, expected in VERSIONS.items():
            try:
                installed = version(package)
            except PackageNotFoundError as exc:
                raise RuntimeError(
                    "Install the integration dependencies: "
                    "python -m pip install -r requirements-mem0.txt"
                ) from exc
            if installed != expected:
                raise RuntimeError(f"Expected {package}=={expected}; found {installed}.")

        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        os.environ["MEM0_TELEMETRY"] = "false"
        os.environ["MEM0_DIR"] = str(self.directory / "config")

        from mem0 import Memory
        from mem0.memory import main

        if main.MEM0_TELEMETRY:
            raise RuntimeError("Start a fresh process so telemetry is disabled before importing Mem0.")

        self._memory_class = Memory
        self.memory = None
        self._open()

    def _open(self):
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "deletion_lab",
                    "path": str(self.directory / "qdrant"),
                    "embedding_model_dims": TokenHashEmbeddings.dimensions,
                    "on_disk": True,
                },
            },
            "history_db_path": str(self.directory / "history.sqlite"),
        }
        # Only the model factories are replaced. Storage and memory APIs are real.
        # The patches end immediately after construction; do not construct adapters
        # concurrently in multiple threads.
        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=TokenHashEmbeddings()),
            patch("mem0.memory.main.LlmFactory.create", return_value=DisabledLLM()),
        ):
            self.memory = self._memory_class.from_config(config)

    def add(self, user_id: str, text: str) -> str:
        result = self.memory.add(text, user_id=user_id, infer=False)
        rows = result["results"]
        if len(rows) != 1 or rows[0].get("event") != "ADD":
            raise RuntimeError("Expected exactly one raw memory to be added.")
        return rows[0]["id"]

    def get(self, memory_id: str):
        return self.memory.get(memory_id)

    def list_memories(self, user_id: str):
        return self.memory.get_all(filters={"user_id": user_id}, top_k=100)["results"]

    def search(self, user_id: str, query: str):
        return self.memory.search(
            query, filters={"user_id": user_id}, top_k=20, threshold=0.0, rerank=False
        )["results"]

    def delete(self, memory_id: str):
        return self.memory.delete(memory_id)

    def history(self, memory_id: str):
        return self.memory.history(memory_id)

    def inspect_point(self, memory_id: str):
        points = self.memory.vector_store.client.retrieve(
            collection_name=self.memory.collection_name,
            ids=[memory_id],
            with_payload=True,
            with_vectors=True,
        )
        return [point.model_dump(mode="json") for point in points]

    def reopen(self):
        self.close()
        self._open()

    def close(self):
        if self.memory is not None:
            memory, self.memory = self.memory, None
            try:
                memory.close()
            finally:
                # Memory.close() in this pin closes history, not the Qdrant client.
                memory.vector_store.client.close()
