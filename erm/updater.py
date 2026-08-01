"""Self-update: check GitHub Releases, download the latest zip,
and hot-swap the app files while preserving data/ and .env.

Only active when running as a frozen PyInstaller bundle.
"""

import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable

GITHUB_REPO = "AhmedArfaouii/Escape_room_game_master_app"
_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def current_version() -> str:
    """Build tag stored in version.txt next to the exe, e.g. 'build-7'."""
    if not is_frozen():
        return "dev"
    p = Path(sys.executable).parent / "version.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else "unknown"


def get_latest_release() -> tuple[str, str, str]:
    """Return (tag, download_url, release_name).  Raises on any error."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx not available")

    resp = httpx.get(
        _API_URL,
        headers={"Accept": "application/vnd.github+json"},
        timeout=10.0,
        follow_redirects=True,
    )
    resp.raise_for_status()
    data = resp.json()
    tag = data["tag_name"]
    name = data.get("name", tag)
    for asset in data.get("assets", []):
        if asset["name"].endswith(".zip"):
            return tag, asset["browser_download_url"], name
    raise RuntimeError("No zip asset found in the latest release")


def download_update(url: str, progress_cb: Callable[[int, int], None]) -> Path:
    """Stream-download the zip.  Calls progress_cb(bytes_done, total_bytes)."""
    import httpx
    import tempfile

    tmp = Path(tempfile.mktemp(suffix=".zip"))
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)
                done += len(chunk)
                progress_cb(done, total)
    return tmp


def install_update(zip_path: Path, tag: str) -> None:
    """Extract zip, stamp version.txt, write an updater bat, and relaunch it.

    The bat runs *after* the app exits, copies new files (skipping data/ and
    media/ so the user's DB and media files are never touched), then restarts.
    """
    app_dir = Path(sys.executable).parent
    extract_dir = app_dir.parent / "_erm_update_tmp"

    # Clean any leftover temp dir
    if extract_dir.exists():
        import shutil
        shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
    zip_path.unlink(missing_ok=True)

    # Stamp the new version so the app knows it after restart
    (extract_dir / "version.txt").write_text(tag + "\n", encoding="utf-8")

    # Bat runs after this process exits:
    #   - robocopy copies everything except data\ media\ .env
    #   - cleans up temp dir
    #   - relaunches the exe
    exe = app_dir / "EscapeRoomMaster.exe"
    bat_path = app_dir / "_erm_updater.bat"
    bat_path.write_text(
        f"@echo off\n"
        f"timeout /t 2 /nobreak >nul\n"
        f'robocopy "{extract_dir}" "{app_dir}" /E /XD "data" "media" /XF ".env" /IS /IT /NFL /NDL /NJH /NJS\n'
        f'rmdir /S /Q "{extract_dir}"\n'
        f'start "" "{exe}"\n'
        f'del "%~f0"\n',
        encoding="utf-8",
    )

    subprocess.Popen(
        ["cmd.exe", "/C", str(bat_path)],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        close_fds=True,
    )
