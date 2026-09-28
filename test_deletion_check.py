from copy import deepcopy
from unittest import TestCase

from deletion_check import check_deletion


class FixtureAdapter:
    """Small contract-test fixture; the integration suite uses actual Mem0."""

    def __init__(self):
        self.rows = {}
        self.points = {}
        self.events = {}
        self.deleted = False
        self.no_search_results = False
        self.ignore_delete = False
        self.delete_everything = False
        self.retain_point = False
        self.break_history = False
        self.queries = []

    def add(self, user_id, text):
        key = str(len(self.rows) + 1)
        self.rows[key] = {"id": key, "user_id": user_id, "memory": text}
        self.points[key] = {"id": key, "payload": {"data": text}, "vector": [1.0]}
        self.events[key] = [{"event": "ADD", "new_memory": text}]
        return key

    def get(self, memory_id):
        return deepcopy(self.rows.get(memory_id))

    def list_memories(self, user_id):
        return deepcopy([row for row in self.rows.values() if row["user_id"] == user_id])

    def search(self, user_id, query):
        self.queries.append(query)
        return [] if self.no_search_results else self.list_memories(user_id)

    def inspect_point(self, memory_id):
        return [deepcopy(self.points[memory_id])] if memory_id in self.points else []

    def history(self, memory_id):
        if self.deleted and self.break_history:
            raise OSError("History is unavailable.")
        return deepcopy(self.events[memory_id])

    def delete(self, memory_id):
        self.deleted = True
        if self.ignore_delete:
            return {"message": "success"}
        old = self.rows.pop(memory_id)
        self.events[memory_id].append({"event": "DELETE", "old_memory": old["memory"]})
        if not self.retain_point:
            self.points.pop(memory_id)
        if self.delete_everything:
            self.rows.clear()
            self.points.clear()
        return {"message": "success"}

    def reopen(self):
        pass


class DeletionRunnerTests(TestCase):
    def test_baseline_failure_is_inconclusive_and_does_not_delete(self):
        adapter = FixtureAdapter()
        adapter.no_search_results = True
        report = check_deletion(adapter)
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertFalse(adapter.deleted)

    def test_success_acknowledgment_does_not_hide_a_noop_delete(self):
        adapter = FixtureAdapter()
        adapter.ignore_delete = True
        report = check_deletion(adapter)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["get_absent"])
        self.assertFalse(report["checks"]["search_absent"])

    def test_empty_search_does_not_prove_the_backend_point_was_deleted(self):
        adapter = FixtureAdapter()
        adapter.retain_point = True
        report = check_deletion(adapter)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(report["checks"]["search_absent"])
        self.assertFalse(report["checks"]["point_absent"])

    def test_overbroad_delete_fails_both_preservation_controls(self):
        adapter = FixtureAdapter()
        adapter.delete_everything = True
        report = check_deletion(adapter)
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["same_user_control_preserved"])
        self.assertFalse(report["checks"]["other_user_control_preserved"])

    def test_history_requirement_changes_the_selected_contract(self):
        normal = check_deletion(FixtureAdapter())
        strict = check_deletion(FixtureAdapter(), require_history_erasure=True)
        self.assertEqual(normal["status"], "PASS")
        self.assertTrue(normal["observations"]["history_marker_retained"])
        self.assertEqual(strict["retrieval_status"], "PASS")
        self.assertEqual(strict["status"], "FAIL")
        self.assertFalse(strict["checks"]["history_marker_absent"])

    def test_inspection_errors_cannot_turn_into_a_pass(self):
        adapter = FixtureAdapter()
        adapter.break_history = True
        report = check_deletion(adapter)
        self.assertEqual(report["status"], "INCONCLUSIVE")
        self.assertEqual(report["error"]["phase"], "inspection after reopen")

    def test_probe_does_not_supply_the_answer(self):
        adapter = FixtureAdapter()
        report = check_deletion(adapter)
        for query in adapter.queries:
            self.assertNotIn(report["fixture"]["marker"], query)
            self.assertNotIn(report["fixture"]["bob_marker"], query)
