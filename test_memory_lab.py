from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from memory_lab import AgentSession, MemoryStore, check_context


class DeletionContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.path = Path(self.directory.name) / "memory.sqlite"
        self.store = MemoryStore(self.path)
        self.marker = "orchid-7412"
        self.store.remember("alice", "shared-id", self.marker)
        self.store.remember("bob", "shared-id", "maple-8531")
        self.original = AgentSession(self.store, "alice")
        self.baseline_seen = any(self.marker in x.text for x in self.original.context)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def reopen(self):
        self.store.close()
        self.store = MemoryStore(self.path)

    def probe(self, session):
        return check_context(session, self.marker, baseline_seen=self.baseline_seen)

    def test_baseline_reaches_the_prompt(self):
        self.assertTrue(self.baseline_seen)
        self.assertIn(self.marker, self.original.make_prompt("What is my project code?"))

    def test_incomplete_delete_is_caught_after_reopening_database(self):
        self.store.delete_record_only("alice", "shared-id")
        self.reopen()
        self.assertEqual(self.store.counts("alice"), {"facts": 0, "summaries": 1})
        result = self.probe(AgentSession(self.store, "alice"))
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["hits"], [{"layer": "summaries", "source_id": "shared-id"}])

    def test_complete_delete_removes_marker_in_fresh_session(self):
        self.store.delete_record_and_summary("alice", "shared-id")
        self.reopen()
        self.assertEqual(self.store.counts("alice"), {"facts": 0, "summaries": 0})
        self.assertEqual(self.probe(AgentSession(self.store, "alice"))["status"], "PASS")

    def test_existing_context_retains_already_loaded_information(self):
        self.store.delete_record_and_summary("alice", "shared-id")
        self.assertEqual(self.probe(self.original)["status"], "FAIL")

    def test_deleting_alice_preserves_bob_with_the_same_memory_id(self):
        self.store.delete_record_and_summary("alice", "shared-id")
        self.reopen()
        bob = AgentSession(self.store, "bob")
        self.assertTrue(any("maple-8531" in x.text for x in bob.context))
        self.assertFalse(any(self.marker in x.text for x in bob.context))

    def test_unconfirmed_setup_cannot_produce_a_pass(self):
        fresh = AgentSession(self.store, "unknown-user")
        result = check_context(fresh, self.marker, baseline_seen=False)
        self.assertEqual(result["status"], "INCONCLUSIVE")


if __name__ == "__main__":
    unittest.main()
