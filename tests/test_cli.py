"""CLI argument parsing tests (no browser launch)."""

import pytest

from chromebrowse.cli import build_parser, main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "chromebrowse" in out


def test_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_info_command(capsys):
    code = main(["info"])
    assert code == 0
    out = capsys.readouterr().out
    assert "chromium" in out
    assert "python" in out


def test_parse_text_command():
    args = build_parser().parse_args(["text", "https://example.com", "--max-chars", "50"])
    assert args.command == "text"
    assert args.url == "https://example.com"
    assert args.max_chars == 50


def test_parse_fetch_flags():
    args = build_parser().parse_args(["fetch", "https://x.test", "--json", "--html", "--links", "--markdown"])
    assert args.json and args.html and args.links and args.markdown


def test_parse_shot_options():
    args = build_parser().parse_args(["shot", "https://x.test", "out.png", "--full", "--type", "jpeg"])
    assert args.output == "out.png"
    assert args.full is True
    assert args.type == "jpeg"


def test_headers_parsing():
    args = build_parser().parse_args(["text", "https://x.test", "--header", "A: 1", "--header", "B:2"])
    assert args.header == ["A: 1", "B:2"]


def test_session_actions_parse():
    for action in ("list", "show", "delete", "clear"):
        args = build_parser().parse_args(["session", action, "mysess"])
        assert args.action == action
        assert args.name == "mysess"


def test_wait_until_choices():
    args = build_parser().parse_args(["text", "https://x.test", "--wait-until", "networkidle"])
    assert args.wait_until == "networkidle"



def test_session_show_reads_persisted_cookies_without_starting_browser(tmp_path, monkeypatch, capsys):
    import json
    from chromebrowse.session import Session

    state_dir = tmp_path / "sessions"
    state_dir.mkdir()
    state = {
        "cookies": [
            {"name": "sid", "value": "abc123", "domain": "example.com"}
        ],
        "origins": [],
    }
    (state_dir / "work.json").write_text(json.dumps(state), encoding="utf-8")

    def fail_start(self):
        raise AssertionError("session show must not launch a browser")

    monkeypatch.setattr(Session, "start", fail_start)
    result = main(["session", "show", "work", "--state-dir", str(state_dir)])
    assert result == 0
    output = capsys.readouterr().out
    assert "1 cookie(s)" in output
    assert "sid=abc123" in output


def test_session_show_json_reads_persisted_cookies(tmp_path, capsys):
    import json

    state_dir = tmp_path / "sessions"
    state_dir.mkdir()
    cookies = [{"name": "sid", "value": "abc123", "domain": "example.com"}]
    (state_dir / "work.json").write_text(
        json.dumps({"cookies": cookies, "origins": []}), encoding="utf-8"
    )

    result = main(["session", "show", "work", "--state-dir", str(state_dir), "--json"])
    assert result == 0
    import json as json_module
    assert json_module.loads(capsys.readouterr().out) == cookies


def test_session_show_missing_state_returns_error(tmp_path, capsys):
    result = main(["session", "show", "missing", "--state-dir", str(tmp_path)])
    assert result == 1
    assert "not found" in capsys.readouterr().err


def test_session_clear_deletes_state_without_launching_browser(tmp_path, monkeypatch, capsys):
    from chromebrowse.session import Session

    state_dir = tmp_path / "sessions"
    state_dir.mkdir()
    state_file = state_dir / "work.json"
    state_file.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    def fail_start(self):
        raise AssertionError("session clear must not launch a browser")

    monkeypatch.setattr(Session, "start", fail_start)
    result = main(["session", "clear", "work", "--state-dir", str(state_dir)])
    assert result == 0
    assert not state_file.exists()
    assert "cleared" in capsys.readouterr().out



def test_fetch_markdown_flag_prints_markdown(monkeypatch, capsys):
    from chromebrowse import cli

    class FakeContent:
        title = "Demo"
        text = "plain text"
        markdown = "# Markdown"

        def as_dict(self):
            return {"text": self.text, "markdown": self.markdown}

    class FakeBrowser:
        def __init__(self, config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def fetch(self, url, **kwargs):
            assert kwargs["include_markdown"] is True
            return FakeContent()

    monkeypatch.setattr(cli, "Browser", FakeBrowser)
    assert main(["fetch", "https://example.com", "--markdown"]) == 0
    assert capsys.readouterr().out == "# Markdown\n"



def test_cli_preserves_explicit_zero_timeout():
    from chromebrowse.cli import _config_from_args, build_parser

    args = build_parser().parse_args(["text", "https://example.com", "--timeout", "0"])
    config = _config_from_args(args)

    assert config.navigation_timeout == 0
    assert config.default_timeout == 0



def test_install_explicit_dir_is_honored_when_chromium_exists_elsewhere(
    tmp_path, monkeypatch, capsys
):
    from chromebrowse import cli, config

    requested_dir = tmp_path / "requested-browsers"
    calls = []

    monkeypatch.setattr(cli, "find_chromium", lambda: "/usr/bin/chromium")

    def fake_install(target_dir, quiet=False):
        calls.append(target_dir)
        return str(requested_dir / "chromium" / "chrome")

    monkeypatch.setattr(config, "install_chromium", fake_install)

    result = main(["install", "--dir", str(requested_dir)])

    assert result == 0
    assert calls == [requested_dir.resolve()]
    assert "Done. Chromium installed at:" in capsys.readouterr().out


def test_interactive_repl_supports_history_reload_help_and_quoted_fill(monkeypatch, capsys):
    from chromebrowse import cli

    commands = iter([
        'fill "input[name=q]" "hello world"',
        "forward",
        "reload",
        "help",
        "quit",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(commands))

    class FakePage:
        title = "Demo"
        fills = []
        actions = []

        def current_url(self):
            return "https://example.com/"

        def fill(self, selector, value):
            self.fills.append((selector, value))

        def go_forward(self):
            self.actions.append("forward")

        def reload(self):
            self.actions.append("reload")

    page = FakePage()

    class FakeBrowser:
        def __init__(self, config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def open(self, url, **kwargs):
            assert url == "https://example.com"
            return page

    monkeypatch.setattr(cli, "Browser", FakeBrowser)
    result = main(["open", "https://example.com"])

    assert result == 0
    assert page.fills == [("input[name=q]", "hello world")]
    assert page.actions == ["forward", "reload"]
    output = capsys.readouterr().out
    assert "Commands:" in output
    assert "at https://example.com/" in output