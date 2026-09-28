"""Run with: python3 demo.py. No packages, credentials, or network required."""

from pathlib import Path
from tempfile import TemporaryDirectory
import json

from memory_lab import AgentSession, MemoryStore, check_context


def run() -> dict:
    marker = "orchid-7412"
    results = {}
    with TemporaryDirectory(prefix="agent-memory-lab-") as directory:
        path = Path(directory) / "memory.sqlite"
        store = MemoryStore(path)
        store.remember("alice", "project-code", f"The synthetic project code is {marker}.")
        store.remember("bob", "project-code", "Bob's synthetic project code is maple-8531.")
        original_session = AgentSession(store, "alice")
        baseline_seen = any(marker in item.text for item in original_session.context)
        assert baseline_seen, "The setup failed to make the marker available."
        print("1. Save a synthetic fact and a separate profile summary.")
        print(json.dumps(store.counts("alice")))

        store.delete_record_only("alice", "project-code")
        print("\n2. Delete only the fact record.")
        print(json.dumps(store.counts("alice")))
        store.close()

        store = MemoryStore(path)
        restarted_session = AgentSession(store, "alice")
        results["incomplete_delete_after_restart"] = check_context(
            restarted_session, marker, baseline_seen=baseline_seen
        )
        print("\n3. Reopen the database and start a fresh session.")
        print(restarted_session.make_prompt("What is my project code?"))
        print(json.dumps(results["incomplete_delete_after_restart"], indent=2))

        store.delete_record_and_summary("alice", "project-code")
        results["old_session_after_complete_delete"] = check_context(
            original_session, marker, baseline_seen=baseline_seen
        )
        store.close()
        store = MemoryStore(path)
        fresh_session = AgentSession(store, "alice")
        results["complete_delete_in_fresh_session"] = check_context(
            fresh_session, marker, baseline_seen=baseline_seen
        )
        print("\n4. Delete both known stored copies and start a fresh session.")
        print(fresh_session.make_prompt("What is my project code?"))
        print(json.dumps(results["complete_delete_in_fresh_session"], indent=2))
        print("\nAn already-built context still needs separate handling:")
        print(json.dumps(results["old_session_after_complete_delete"], indent=2))
        assert any("maple-8531" in item.text for item in store.read_context("bob"))
        store.close()

    assert results["incomplete_delete_after_restart"]["status"] == "FAIL"
    assert results["old_session_after_complete_delete"]["status"] == "FAIL"
    assert results["complete_delete_in_fresh_session"]["status"] == "PASS"
    print("\nExpected results confirmed; Bob's data stayed intact.")
    print("FAIL above means the check caught an intentional teaching defect.")
    print("No LLM was called. This checks context assembly, not generated answers.")
    return results


if __name__ == "__main__":
    run()
