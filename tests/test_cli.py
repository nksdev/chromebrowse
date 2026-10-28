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
    args = build_parser().parse_args(["fetch", "https://x.test", "--json", "--html", "--links"])
    assert args.json and args.html and args.links


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
