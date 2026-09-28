"""Run the real storage experiment and write a machine-readable report."""

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
import logging
from pathlib import Path
from platform import python_version
from uuid import uuid4

from deletion_check import check_deletion
from mem0_adapter import Mem0Adapter, VERSIONS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, help="A new, nonexistent directory for this run.")
    parser.add_argument("--require-history-erasure", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print only the JSON report to stdout.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.ERROR)
    directory = (args.data_dir or Path(".lab") / f"mem0-{uuid4().hex[:12]}").resolve()
    adapter = None
    created = False
    report = {"schema_version": 1, "status": "INCONCLUSIVE"}
    try:
        directory.mkdir(parents=True, exist_ok=False)
        created = True
        adapter = Mem0Adapter(directory)
        report = check_deletion(adapter, require_history_erasure=args.require_history_erasure)
    except Exception as exc:
        report["reason"] = "The experiment could not start; no passing result is available."
        report["error"] = {"phase": "initialization", "type": type(exc).__name__, "message": str(exc)}
    finally:
        if adapter is not None:
            try:
                adapter.close()
            except Exception as exc:
                report["status"] = "INCONCLUSIVE"
                report["error"] = {"phase": "close", "type": type(exc).__name__, "message": str(exc)}

    installed = {}
    for package in VERSIONS:
        try:
            installed[package] = version(package)
        except PackageNotFoundError:
            installed[package] = None
    report["environment"] = {
        "required_versions": VERSIONS,
        "installed_versions": installed,
        "python": python_version(),
        "backend": "Qdrant local, on disk",
        "embeddings": "128-dimensional token hashes; no semantic model",
        "inference": False,
        "llm": "disabled; any call raises",
        "telemetry": False,
    }
    report["data_directory"] = str(directory)
    output = directory / "report.json"
    if created:
        try:
            output.write_text(json.dumps(report, indent=2) + "\n")
        except OSError as exc:
            report["status"] = "INCONCLUSIVE"
            report["error"] = {"phase": "write report", "type": type(exc).__name__, "message": str(exc)}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Mem0 deletion experiment: {report['status']}")
        print(f"Contract: {report.get('contract', 'not started')}")
        for name, passed in report.get("checks", {}).items():
            print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        for name, retained in report.get("observations", {}).items():
            if name.endswith("_retained"):
                print(f"  {'RETAINED' if retained else 'ABSENT'}  {name}")
        if "error" in report:
            print(f"Error: {report['error']}")
        if created and output.is_file():
            print(f"Report and synthetic data: {directory}")
        print("No LLM was called. PASS applies only to the selected, inspected scope.")
    return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
