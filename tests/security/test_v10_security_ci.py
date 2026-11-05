"""V10 - the pipeline itself: the security suite must FAIL when a control is deliberately broken."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ["tests/security/test_v07_access_control.py", "-q", "-x", "-p", "no:cacheprovider"]


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_extra, "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-m", "pytest", *CORE], cwd=ROOT, env=env, capture_output=True, text=True, check=False)


def test_intentional_isolation_bug_makes_the_suite_fail():
    broken = _run({"SIMULATE_ISOLATION_BUG": "1"})
    assert broken.returncode != 0, "CI would have let a cross-plant leak through!\n" + broken.stdout[-800:]


def test_suite_passes_again_after_the_fix():
    ok = _run({})
    assert ok.returncode == 0, ok.stdout[-800:]
