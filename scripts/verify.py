"""Run the final gate, preserving actual command output and exit codes."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser-channel", help="Use installed chrome or msedge instead of bundled Chromium")
    parser.add_argument("--skip-ui", action="store_true", help="Explicitly report UI test as skipped")
    args = parser.parse_args()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise SystemExit("npm is required; install Node.js 22.12+ first")
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    commands = [
        [sys.executable, "-m", "pytest", "backend/tests", "-q", "--junitxml=evidence/backend-tests.xml"],
        [npm, "--prefix", "frontend", "run", "build"],
        [npm, "--prefix", "frontend", "run", "format:check"],
        [npm, "--prefix", "frontend", "audit", "--audit-level=moderate"],
        [sys.executable, "scripts/benchmark.py", "--mode", "both"],
    ]
    if not args.skip_ui:
        commands.append([npm, "--prefix", "frontend", "run", "test:ui"])
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if args.browser_channel:
        env["PLAYWRIGHT_CHANNEL"] = args.browser_channel
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.system(), "python": platform.python_version(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "ui": "explicitly skipped" if args.skip_ui else args.browser_channel or "bundled chromium",
              "checks": []}
    for command in commands:
        display = subprocess.list2cmdline(command).replace(str(ROOT), "<repo>")
        print(f"Running {display}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
        output = result.stdout.replace(str(ROOT), "<repo>")
        print(output, flush=True)
        report["checks"].append({"command": display, "exit_code": result.returncode, "output": output})
        (evidence / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return int(any(check["exit_code"] for check in report["checks"]))


if __name__ == "__main__":
    sys.exit(main())
