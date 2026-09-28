from contextlib import ExitStack, redirect_stdout
from importlib.util import find_spec
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from deletion_check import check_deletion
from mem0_adapter import Mem0Adapter
from mem0_demo import main


@unittest.skipUnless(find_spec("mem0") and find_spec("qdrant_client"), "Install requirements-mem0.txt for integration tests")
class Mem0IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.directory = Path(self.stack.enter_context(TemporaryDirectory()))
        # Downloads are an install-time step. The complete experiment must run offline.
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.getaddrinfo"):
            guard = self.stack.enter_context(patch(target, side_effect=AssertionError("Unexpected network access")))
            self.addCleanup(guard.assert_not_called)

    def adapter(self):
        adapter = Mem0Adapter(self.directory / "data")
        self.addCleanup(adapter.close)
        return adapter

    def test_real_storage_deletion_and_history_after_reopen(self):
        report = check_deletion(self.adapter())
        self.assertEqual(report["status"], "PASS", report)
        self.assertTrue(all(report["baseline"].values()))
        self.assertTrue(all(report["checks"].values()))
        point = report["before"]["point"][0]
        self.assertEqual(len(point["vector"]), 128)
        self.assertIn(report["fixture"]["marker"], point["payload"]["data"])
        self.assertEqual(report["after"]["point"], [])
        self.assertEqual([row["event"] for row in report["after"]["history"]], ["ADD", "DELETE"])
        self.assertTrue(report["observations"]["history_marker_retained"])
        self.assertTrue(report["observations"]["old_context_marker_retained"])

    def test_stricter_contract_fails_on_retained_history(self):
        report = check_deletion(self.adapter(), require_history_erasure=True)
        self.assertEqual(report["status"], "FAIL", report)
        self.assertEqual(report["retrieval_status"], "PASS")
        self.assertFalse(report["checks"]["history_marker_absent"])

    def test_cli_emits_json_and_failure_exit_code_for_strict_contract(self):
        output = StringIO()
        directory = self.directory / "cli"
        with redirect_stdout(output):
            code = main(["--data-dir", str(directory), "--require-history-erasure", "--json"])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(json.loads((directory / "report.json").read_text()), report)

    def test_existing_directory_is_untouched(self):
        sentinel = self.directory / "keep.txt"
        sentinel.write_text("keep this")
        with redirect_stdout(StringIO()):
            code = main(["--data-dir", str(self.directory), "--json"])
        self.assertEqual(code, 2)
        self.assertEqual(sentinel.read_text(), "keep this")
        self.assertEqual(list(self.directory.iterdir()), [sentinel])
