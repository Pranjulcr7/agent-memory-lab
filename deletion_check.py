"""A finite deletion contract with baseline and preservation controls."""

import json
from typing import Protocol
from uuid import uuid4


class MemoryAdapter(Protocol):
    def add(self, user_id: str, text: str) -> str: ...
    def get(self, memory_id: str) -> dict | None: ...
    def list_memories(self, user_id: str) -> list[dict]: ...
    def search(self, user_id: str, query: str) -> list[dict]: ...
    def delete(self, memory_id: str): ...
    def history(self, memory_id: str) -> list[dict]: ...
    def inspect_point(self, memory_id: str) -> list[dict]: ...
    def reopen(self): ...


def has_marker(value, marker):
    return marker in json.dumps(value, sort_keys=True)


def has_id(rows, memory_id):
    return any(row.get("id") == memory_id for row in rows)


def check_deletion(adapter: MemoryAdapter, *, require_history_erasure=False):
    run_id = uuid4().hex
    alice, bob = f"alice-{run_id}", f"bob-{run_id}"
    marker, bob_marker = f"orchid-{run_id}", f"maple-{run_id}"
    query = "What is my project code?"
    keep_text = "My preferred programming language is Python."
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "INCONCLUSIVE",
        "contract": "retrieval-and-history" if require_history_erasure else "retrieval",
        "query": query,
        "coverage": {
            "inspected": ["get by ID", "scoped list", "scoped search", "Qdrant point", "history by ID"],
            "not_tested": [
                "generated answers", "semantic paraphrases", "inferred memories and entities",
                "application summaries and caches", "chat transcripts", "backups",
                "physical disk erasure", "concurrent requests", "authorization enforcement",
            ],
            "restart": "close and reopen clients against the same local files",
            "fixture_size": "three records; not a pagination or scale test",
        },
        "checks": {},
    }
    phase = "setup"
    try:
        target = adapter.add(alice, f"My project code is {marker}.")
        keep = adapter.add(alice, keep_text)
        other = adapter.add(bob, f"My project code is {bob_marker}.")
        report["fixture"] = {
            "alice": alice, "bob": bob, "marker": marker, "bob_marker": bob_marker,
            "target_id": target, "same_user_control_id": keep, "other_user_control_id": other,
        }

        phase = "baseline after reopen"
        adapter.reopen()
        before = {
            "get": adapter.get(target),
            "list": adapter.list_memories(alice),
            "search": adapter.search(alice, query),
            "point": adapter.inspect_point(target),
            "history": adapter.history(target),
            "same_user_control": adapter.get(keep),
            "other_user_control": adapter.get(other),
            "other_user_search": adapter.search(bob, query),
        }
        report["before"] = before
        baseline = {
            "target_in_get": before["get"] is not None and has_marker(before["get"], marker),
            "target_in_list": has_id(before["list"], target) and has_marker(before["list"], marker),
            "target_in_search": has_id(before["search"], target) and has_marker(before["search"], marker),
            "target_in_point": has_id(before["point"], target) and has_marker(before["point"], marker),
            "target_in_history": has_marker(before["history"], marker),
            "same_user_control": before["same_user_control"] is not None
                and before["same_user_control"].get("memory") == keep_text,
            "other_user_control": before["other_user_control"] is not None
                and has_marker(before["other_user_control"], bob_marker)
                and has_id(before["other_user_search"], other),
            "separate_users": not has_marker(before["search"], bob_marker)
                and not has_marker(before["other_user_search"], marker),
        }
        report["baseline"] = baseline
        if not all(baseline.values()):
            report["reason"] = "The baseline did not confirm every required surface and control."
            return report

        phase = "delete"
        report["delete_response"] = adapter.delete(target)
        phase = "inspection after reopen"
        adapter.reopen()
        after = {
            "get": adapter.get(target),
            "list": adapter.list_memories(alice),
            "search": adapter.search(alice, query),
            "point": adapter.inspect_point(target),
            "history": adapter.history(target),
            "same_user_control": adapter.get(keep),
            "other_user_control": adapter.get(other),
            "other_user_search": adapter.search(bob, query),
        }
        report["after"] = after
        checks = {
            "get_absent": after["get"] is None,
            "list_absent": not has_id(after["list"], target) and not has_marker(after["list"], marker),
            "search_absent": not has_id(after["search"], target) and not has_marker(after["search"], marker),
            "point_absent": after["point"] == [],
            "same_user_control_preserved": after["same_user_control"] == before["same_user_control"]
                and has_id(after["list"], keep),
            "other_user_control_preserved": after["other_user_control"] == before["other_user_control"]
                and has_id(after["other_user_search"], other)
                and has_marker(after["other_user_search"], bob_marker),
            "scoped_searches": not has_marker(after["search"], bob_marker)
                and not has_marker(after["other_user_search"], marker),
        }
        report["retrieval_status"] = "PASS" if all(checks.values()) else "FAIL"
        history_retained = has_marker(after["history"], marker)
        report["observations"] = {
            "history_marker_retained": history_retained,
            "old_context_marker_retained": has_marker(before["search"], marker),
            "history_note": "History is not automatically supplied to an agent by this adapter.",
        }
        if require_history_erasure:
            checks["history_marker_absent"] = not history_retained
        report["checks"] = checks
        report["status"] = "PASS" if all(checks.values()) else "FAIL"
        report["reason"] = "All checks passed for the selected scope." if report["status"] == "PASS" else "One or more selected checks failed."
    except Exception as exc:
        report["status"] = "INCONCLUSIVE"
        report["reason"] = "The run could not complete; missing evidence is not a pass."
        report["error"] = {"phase": phase, "type": type(exc).__name__, "message": str(exc)}
    return report
