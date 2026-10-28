"""Tests for the python -m chromebrowse command."""

import subprocess
import sys


def test_python_m_chromebrowse_version():
    result = subprocess.run(
        [sys.executable, "-m", "chromebrowse", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "chromebrowse" in result.stdout
