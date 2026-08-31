"""
Issue #16: requirements.txt reflected the old TensorFlow-based setup and had
no references from code, CI, or docs. Verifies it stays gone and that no
file in the repo (besides this test and CI/docs prose) references it as a
dependency source.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_requirements_txt_does_not_exist():
    assert not (ROOT / "requirements.txt").exists()


def test_no_pip_install_dash_r_requirements_reference():
    result = subprocess.run(
        ["git", "grep", "-l", "-i", "pip install -r requirements"],
        cwd=ROOT, capture_output=True, text=True,
    )
    # git grep exits 1 when there are no matches - that's the expected state.
    assert result.returncode == 1, f"unexpected reference(s) found:\n{result.stdout}"
