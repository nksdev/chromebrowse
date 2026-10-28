"""Configuration objects and Chromium binary discovery."""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .exceptions import ChromiumNotFoundError

ENV_BROWSERS_PATH = "PLAYWRIGHT_BROWSERS_PATH"
ENV_CHROMIUM_EXECUTABLE = "CHROMEBROWSE_CHROMIUM"

# Let Playwright derive a user agent from the actual Chromium build and OS.
# A hard-coded Windows/old-Chrome UA is misleading on macOS/Linux and drifts
# away from the browser version shipped by Playwright.
DEFAULT_USER_AGENT: Optional[str] = None


def _platform_tokens() -> List[str]:
    """Tokens used by Playwright's browser directory names."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    tokens: List[str] = []
    if system == "darwin":
        tokens.append("mac")
        tokens.append("arm64" if machine in ("arm64", "aarch64") else "x64")
    elif system == "windows":
        tokens.append("win64")
    else:
        tokens.append("linux")
        tokens.append("arm64" if machine in ("arm64", "aarch64") else "x64")
    return tokens


def _playwright_browsers_dirs() -> List[Path]:
    """Candidate directories where Playwright stores browsers."""
    dirs: List[Path] = []

    env = os.environ.get(ENV_BROWSERS_PATH)
    if env and env != "0":
        dirs.append(Path(env).expanduser())

    # Project-local directory next to this package (used by the bundled install).
    here = Path(__file__).resolve()
    for parent in list(here.parents)[:6]:
        cand = parent / ".browsers"
        if cand.is_dir():
            dirs.append(cand)

    system = platform.system().lower()
    if system == "darwin":
        dirs.append(Path.home() / "Library" / "Caches" / "ms-playwright")
    elif system == "windows":
        local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        dirs.append(Path(local) / "ms-playwright")
    else:
        dirs.append(Path.home() / ".cache" / "ms-playwright")

    # De-duplicate while preserving order.
    seen = set()
    out = []
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def _executable_in(browser_dir: Path) -> Optional[Path]:
    """Return the Chromium executable inside a Playwright browser folder."""
    system = platform.system().lower()
    if system == "darwin":
        rel = Path("chrome-mac") / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        rel_arm = Path("chrome-mac-arm64") / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        for r in (rel_arm, rel):
            p = browser_dir / r
            if p.is_file():
                return p
        # Chrome for Testing layout
        for p in browser_dir.glob("chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"):
            if p.is_file():
                return p
    elif system == "windows":
        for name in ("chrome-win/chrome.exe", "chrome-win64/chrome.exe"):
            p = browser_dir / name
            if p.is_file():
                return p
    else:
        for name in ("chrome-linux/chrome", "chrome-linux64/chrome"):
            p = browser_dir / name
            if p.is_file():
                return p
    return None


def find_chromium() -> Optional[str]:
    """Locate a usable Chromium executable.

    Order of preference:
      1. ``CHROMEBROWSE_CHROMIUM`` environment variable.
      2. Playwright-managed Chromium (project local or user cache).
      3. System Chrome/Chromium/Edge installation.

    Returns ``None`` if nothing is found.
    """
    env = os.environ.get(ENV_CHROMIUM_EXECUTABLE)
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return str(p)

    for base in _playwright_browsers_dirs():
        if not base.is_dir():
            continue
        # Prefer full chromium builds over headless shells.
        candidates = sorted(
            [d for d in base.glob("chromium-*") if d.is_dir()],
            reverse=True,
        )
        for c in candidates:
            exe = _executable_in(c)
            if exe:
                return str(exe)

    system = platform.system().lower()
    names: List[str] = []
    if system == "darwin":
        names = [
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif system == "windows":
        names = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        names = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/snap/bin/chromium",
        ]
        for n in ("chromium", "chromium-browser", "google-chrome"):
            found = shutil.which(n)
            if found:
                names.insert(0, found)

    for n in names:
        if Path(n).is_file():
            return n
    return None


def require_chromium() -> str:
    exe = find_chromium()
    if not exe:
        raise ChromiumNotFoundError(
            "No Chromium executable found. Install one with:\n"
            "    chromebrowse install\n"
            "or set CHROMEBROWSE_CHROMIUM to an existing Chrome/Chromium binary.\n"
            "Or let chromebrowse fetch it automatically: Browser(auto_install=True)"
        )
    return exe


def default_install_dir() -> Path:
    """Writable directory used for an auto-downloaded Chromium."""
    import os

    env = os.environ.get("CHROMEBROWSE_BROWSERS_DIR")
    if env:
        return Path(env).expanduser()

    here = Path(__file__).resolve()
    for parent in list(here.parents)[:6]:
        cand = parent / ".browsers"
        if cand.is_dir():
            return cand

    home = Path.home()
    try:
        if os.access(home, os.W_OK):
            return home / ".chromebrowse" / "browsers"
    except OSError:
        pass

    return Path.cwd() / ".browsers"


def install_chromium(
    target_dir: Optional[Union[str, Path]] = None,
    quiet: bool = False,
) -> str:
    """Download Chromium into ``target_dir`` and return the executable path.

    Uses the Playwright installer under the hood so the result matches what
    :func:`find_chromium` already knows how to discover.
    """
    import subprocess
    import sys

    target = Path(target_dir).expanduser().resolve() if target_dir else default_install_dir()
    target.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(target)

    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    stdout = subprocess.DEVNULL if quiet else None
    result = subprocess.run(cmd, env=env, stdout=stdout, stderr=stdout)
    if result.returncode != 0:
        raise ChromiumNotFoundError(
            f"automatic Chromium download failed (exit {result.returncode}). "
            "Run 'chromebrowse install' manually for details."
        )

    # Make the fresh install discoverable for the rest of this process.
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(target)

    # Look only inside ``target`` so a stale copy elsewhere cannot mask it.
    for browser_dir in sorted(
        [d for d in target.glob("chromium-*") if d.is_dir()], reverse=True
    ):
        exe = _executable_in(browser_dir)
        if exe:
            return str(exe)

    raise ChromiumNotFoundError(
        f"Chromium downloaded to {target} but no executable was found there."
    )


@dataclass
class BrowserConfig:
    """Options controlling a :class:`~chromebrowse.Browser` instance."""

    headless: bool = True
    executable_path: Optional[str] = None
    user_agent: Optional[str] = DEFAULT_USER_AGENT
    viewport_width: int = 1280
    viewport_height: int = 800
    locale: str = "en-US"
    timezone: Optional[str] = None
    default_timeout: float = 30_000.0  # milliseconds
    navigation_timeout: float = 45_000.0  # milliseconds
    ignore_https_errors: bool = False
    java_script_enabled: bool = True
    block_images: bool = False
    block_resources: List[str] = field(default_factory=list)
    extra_headers: Dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    user_data_dir: Optional[str] = None  # persistent context when set
    slow_mo: float = 0.0
    args: List[str] = field(default_factory=list)
    downloads_path: Optional[str] = None
    auto_install: bool = True  # download Chromium on first launch if missing
    install_dir: Optional[str] = None  # where auto_install places Chromium
    prompt_install: bool = False  # ask before downloading (off: download silently)
    public_only: bool = False  # reject non-public HTTP(S) requests; see SSRF caveat

    def resolve_executable(self) -> Optional[str]:
        if self.executable_path:
            return self.executable_path
        return find_chromium()

    def to_launch_kwargs(self) -> Dict[str, Any]:
        exe = self.resolve_executable()
        kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
        }
        if exe:
            kwargs["executable_path"] = exe
        if self.proxy:
            kwargs["proxy"] = {"server": self.proxy}
        if self.args:
            kwargs["args"] = list(self.args)
        if self.downloads_path:
            kwargs["downloads_path"] = self.downloads_path
        return kwargs

    def context_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "user_agent": self.user_agent,
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "locale": self.locale,
            "ignore_https_errors": self.ignore_https_errors,
            "java_script_enabled": self.java_script_enabled,
            "extra_http_headers": dict(self.extra_headers) or None,
        }
        if self.timezone:
            kwargs["timezone_id"] = self.timezone
        # Proxy is configured at BrowserType.launch / launch_persistent_context.
        # Duplicating it here makes launch_persistent_context receive the same
        # keyword twice and fail before Chromium starts.
        return {k: v for k, v in kwargs.items() if v is not None}

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrowserConfig":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def platform_info() -> Dict[str, Any]:
    """Diagnostics describing the current runtime."""
    exe = find_chromium()
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "chromium": exe,
        "chromium_found": bool(exe),
        "browsers_dirs": [str(d) for d in _playwright_browsers_dirs()],
    }