import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chromebrowse.session import Session, _restrict_permissions, _local_storage_seed_script


def test_load_state_restores_cookies_and_origins(tmp_path):
    state = tmp_path / "s.json"
    state.write_text(json.dumps({
        "cookies": [{"name": "a", "value": "b", "domain": "x.com", "path": "/"}],
        "origins": [{"origin": "https://x.com", "localStorage": [{"name": "tok", "value": "123"}]}],
    }))

    s = Session("t", state_dir=tmp_path)
    s._browser = MagicMock()
    s._load_state_file(state)

    s._browser.context.add_cookies.assert_called_once()
    script = s._browser.context.add_init_script.call_args.kwargs["script"]
    assert "https://x.com" in script
    assert "tok" in script
    assert "123" in script


def test_load_state_without_origins_only_sets_cookies(tmp_path):
    state = tmp_path / "s.json"
    state.write_text(json.dumps({"cookies": [{"name": "a", "value": "b"}]}))

    s = Session("t", state_dir=tmp_path)
    s._browser = MagicMock()
    s._load_state_file(state)

    s._browser.context.add_cookies.assert_called_once()
    s._browser.context.add_init_script.assert_not_called()


def test_load_state_rejects_non_object(tmp_path):
    from chromebrowse.exceptions import SessionError
    state = tmp_path / "s.json"
    state.write_text(json.dumps([1, 2, 3]))
    s = Session("t", state_dir=tmp_path)
    s._browser = MagicMock()
    with pytest.raises(SessionError):
        s._load_state_file(state)


def test_save_restricts_permissions(tmp_path):
    if os.name == "nt":
        pytest.skip("POSIX permissions")
    target = tmp_path / "state.json"
    target.write_text("{}")
    os.chmod(target, 0o644)
    _restrict_permissions(target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_restrict_permissions_is_best_effort(tmp_path):
    _restrict_permissions(tmp_path / "does-not-exist.json")


def test_seed_script_isolates_origins():
    script = _local_storage_seed_script("https://a.com", [{"name": "k", "value": "v"}])
    assert "https://a.com" in script
    assert "location.origin" in script


def test_fetch_does_not_leak_extraction_flags(tmp_path):
    s = Session("t", state_dir=tmp_path)
    page = MagicMock()
    page.extract.return_value = "CONTENT"
    s._browser = MagicMock()
    s._page = page
    with patch.object(Session, "open", return_value=page) as mock_open:
        out = s.fetch("https://x", include_html=True, include_links=True, wait_until="load")
    assert out == "CONTENT"
    mock_open.assert_called_once_with("https://x", wait_until="load")
    page.extract.assert_called_once_with(include_html=True, include_links=True)
