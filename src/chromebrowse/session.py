"""Persistent browser sessions with cookie / storage-state support."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .browser import Browser, Page
from .config import BrowserConfig
from .exceptions import SessionError

def _default_state_dir() -> Path:
    """Pick a writable directory for persisted session state.

    Preference order:
      1. ``CHROMEBROWSE_STATE_DIR`` environment variable.
      2. ``$XDG_STATE_HOME/chromebrowse/sessions`` (Linux convention).
      3. ``~/.chromebrowse/sessions`` when the home directory is writable.
      4. ``./.chromebrowse/sessions`` in the current working directory.
    """
    import os

    env = os.environ.get("CHROMEBROWSE_STATE_DIR")
    if env:
        return Path(env).expanduser()

    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        cand = Path(xdg).expanduser() / "chromebrowse" / "sessions"
        try:
            cand.mkdir(parents=True, exist_ok=True)
            return cand
        except OSError:
            pass

    home = Path.home()
    try:
        if os.access(home, os.W_OK):
            cand = home / ".chromebrowse" / "sessions"
            cand.mkdir(parents=True, exist_ok=True)
            return cand
    except OSError:
        pass

    return Path.cwd() / ".chromebrowse" / "sessions"


DEFAULT_STATE_DIR = _default_state_dir()


def _restrict_permissions(path: Path) -> None:
    """Best-effort ``chmod 0600`` on a state file holding credentials."""
    import os
    import stat

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, NotImplementedError):
        # Windows and some network filesystems do not support POSIX modes.
        pass


def _local_storage_seed_script(origin: str, items: List[Dict[str, Any]]) -> str:
    """Build an init script that repopulates localStorage for one origin.

    ``add_init_script`` runs in every frame before page scripts, so the guard
    on ``location.origin`` keeps each origin's data isolated.
    """
    payload = json.dumps({i.get("name"): i.get("value") for i in items})
    return (
        "(() => {\n"
        f"  if (window.location.origin !== {json.dumps(origin)}) return;\n"
        f"  const data = {payload};\n"
        "  for (const [k, v] of Object.entries(data)) {\n"
        "    try { window.localStorage.setItem(k, v); } catch (e) {}\n"
        "  }\n"
        "})();"
    )


class Session:
    """A named, persistable browsing session.

    A session owns one :class:`~chromebrowse.Browser` plus an optional
    storage-state file holding cookies and localStorage.  Use it when you
    need to stay logged in across runs::

        from chromebrowse import Session

        with Session("github") as s:
            s.open("https://github.com/login")
            s.page.fill("#login_field", "me")
            s.page.fill("#password", "secret")
            s.page.click("[name=commit]")
            s.save()
    """

    def __init__(
        self,
        name: str = "default",
        config: Optional[BrowserConfig] = None,
        state_dir: Optional[Union[str, Path]] = None,
        persist: bool = True,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.config = config or BrowserConfig(**kwargs)
        self.state_dir = Path(state_dir).expanduser() if state_dir else DEFAULT_STATE_DIR
        self.persist = persist
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------ properties
    @property
    def state_path(self) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.name)
        return self.state_dir / f"{safe}.json"

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            self.start()
        assert self._browser is not None
        return self._browser

    @property
    def page(self) -> Page:
        if self._page is None:
            self._page = self.browser.new_page()
        return self._page

    # -------------------------------------------------------------- lifecycle
    def start(self) -> "Session":
        if self._browser is not None:
            return self
        self._browser = Browser(self.config)
        self._browser.start()
        if self.persist and self.state_path.is_file():
            try:
                self._load_state_file(self.state_path)
            except SessionError:
                pass  # corrupt state should not block startup
        return self

    def _load_state_file(self, path: Path) -> None:
        """Restore a full Playwright storage state (cookies *and* origins).

        Playwright's storage state is a superset of cookies: it also carries
        per-origin ``localStorage`` snapshots, which many modern sites use for
        auth tokens.  Applying only ``cookies`` silently logs the user out on
        those sites, so both sections are restored here.
        """
        assert self._browser is not None
        try:
            data = json.loads(path.read_text("utf-8"))
        except Exception as exc:
            raise SessionError(f"cannot read state {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise SessionError(f"invalid state {path}: expected a JSON object")

        cookies = data.get("cookies") or []
        if cookies:
            try:
                self._browser.context.add_cookies(cookies)
            except Exception as exc:
                raise SessionError(f"cannot apply cookies: {exc}") from exc

        for origin in data.get("origins") or []:
            origin_url = origin.get("origin")
            items = origin.get("localStorage") or []
            if not origin_url or not items:
                continue
            try:
                # Seed localStorage before the page's own scripts run.
                self._browser.context.add_init_script(
                    script=_local_storage_seed_script(origin_url, items)
                )
            except Exception as exc:
                raise SessionError(
                    f"cannot restore localStorage for {origin_url}: {exc}"
                ) from exc

    def save(self) -> str:
        """Persist cookies + localStorage to the session state file.

        The file contains live authentication material, so it is written with
        owner-only permissions (``0600``) on POSIX systems.
        """
        assert self._browser is not None, "session not started"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._browser.context.storage_state(path=str(self.state_path))
        _restrict_permissions(self.state_path)
        return str(self.state_path)

    def clear(self) -> None:
        """Delete persisted state and clear in-memory cookies."""
        if self.state_path.is_file():
            self.state_path.unlink()
        if self._browser is not None:
            try:
                self._browser.context.clear_cookies()
            except Exception:
                pass

    def close(self) -> None:
        if self._browser is not None:
            if self.persist:
                try:
                    self.save()
                except Exception:
                    pass
            self._browser.close()
        self._browser = None
        self._page = None

    # ----------------------------------------------------------- convenience
    def open(self, url: str, **kwargs: Any) -> Page:
        self.start()
        self._page = self.browser.open(url, page=self._page, **kwargs)
        return self._page

    def fetch(
        self,
        url: str,
        include_html: bool = False,
        include_links: bool = False,
        **kwargs: Any,
    ):
        """Navigate and extract in one call.

        Extraction flags are named parameters rather than ``kwargs`` so they
        cannot leak into the navigation call.
        """
        page = self.open(url, **kwargs)
        return page.extract(include_html=include_html, include_links=include_links)

    def cookies(self) -> List[Dict[str, Any]]:
        return self.browser.context.cookies()

    def add_cookies(self, cookies: List[Dict[str, Any]]) -> "Session":
        self.browser.context.add_cookies(cookies)
        return self

    def __enter__(self) -> "Session":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Session {self.name!r} state={str(self.state_path)!r}>"


# ------------------------------------------------------------------ registry
def list_sessions(state_dir: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """List persisted sessions with size and modification time."""
    directory = Path(state_dir).expanduser() if state_dir else DEFAULT_STATE_DIR
    if not directory.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for f in sorted(directory.glob("*.json")):
        st = f.stat()
        out.append(
            {
                "name": f.stem,
                "path": str(f),
                "bytes": st.st_size,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
            }
        )
    return out


def delete_session(name: str, state_dir: Optional[Union[str, Path]] = None) -> bool:
    directory = Path(state_dir).expanduser() if state_dir else DEFAULT_STATE_DIR
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    target = directory / f"{safe}.json"
    if target.is_file():
        target.unlink()
        return True
    return False
