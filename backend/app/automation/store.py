"""Playwright automation projects stored as safe folders of .py scripts on disk."""
import os
import re
from datetime import datetime
from pathlib import Path

from app.config.settings import settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]")
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")
_ALLOWED_PROJECT = re.compile(r"[^A-Za-z0-9 ._-]")


def root() -> Path:
    return Path(settings.AUTOMATION_PATH) / "projects"


def safe_project(name: str) -> str:
    """Reduce an arbitrary project name to one safe folder component. Mid-name
    spaces are kept so the name reads naturally in the scheduler dropdown;
    filesystem safety still comes from the resolve()/is_relative_to guard."""
    cleaned = _ALLOWED_PROJECT.sub("_", (name or "").replace("\t", " ").strip()).strip("._ ")
    if not cleaned:
        raise ValueError("Project name cannot be empty")
    return cleaned[:60]


def safe_file(name: str) -> str:
    """Python file names must be a single safe component ending in .py."""
    cleaned = _SAFE.sub("_", (name or "").strip()).strip("._")
    if not cleaned:
        raise ValueError("File name cannot be empty")
    if not cleaned.lower().endswith(".py"):
        cleaned = f"{cleaned}.py"
    return cleaned[:120]


def folder(project: str) -> Path:
    base = root().resolve()
    target = (base / safe_project(project)).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Invalid project name")
    return target


def file_path(project: str, name: str) -> Path:
    base = folder(project).resolve()
    target = (base / safe_file(name)).resolve()
    if not target.is_relative_to(base) or target.suffix.lower() != ".py":
        raise ValueError("Invalid file name")
    return target


def exists(project: str) -> bool:
    return folder(project).joinpath("main.py").is_file()


def list_projects() -> list[dict]:
    result = []
    base = root()
    if not base.is_dir():
        return result
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir():
            continue
        # Shared helper folders (``_lib``) are not runnable projects.
        if entry.name.startswith((".", "_")):
            continue
        files = [f.name for f in sorted(entry.iterdir()) if f.is_file() and f.suffix.lower() == ".py"]
        stat = entry.stat()
        result.append({"name": entry.name, "files": files,
                       "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    return result


def list_files(project: str) -> list[str]:
    base = folder(project)
    if not base.is_dir():
        raise LookupError("Project not found")
    return [f.name for f in sorted(base.iterdir()) if f.is_file() and f.suffix.lower() == ".py"]


def read(project: str, name: str) -> dict | None:
    path = file_path(project, name)
    if not path.is_file():
        return None
    return {"name": path.name, "content": path.read_text(encoding="utf-8", errors="replace")}


def write(project: str, name: str, content: str) -> str:
    path = file_path(project, name)
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")
    return path.name


def delete_file(project: str, name: str) -> bool:
    path = file_path(project, name)
    if not path.is_file():
        return False
    path.unlink()
    return True


def delete_project(project: str) -> bool:
    base = folder(project)
    if not base.exists():
        return False
    import shutil
    shutil.rmtree(base)
    return True


TEMPLATE_MAIN = '''"""Web Automation Demo — Playwright (Python)

Runs unattended in Playwright's own headless Chromium. Edit this file freely.
Keep this project to plain Python: the scheduler runs main.py on its schedule.

Fails hard when the checked condition does not match, so the scheduler records
the run as failed and you can inspect its output log.
"""
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "https://example.com"
ARTIFACTS = Path(__file__).parent / "artifacts"


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, timeout=30000)
        page.wait_for_load_state("networkidle")
        title = page.title()
        page.screenshot(path=ARTIFACTS / f"{datetime.now():%Y-%m-%d_%H%M%S}.png")
        print(f"Opened {URL}")
        print(f"Page title: {title}")
        browser.close()

    assert title == "Example Domain", f"Unexpected title: {title!r}"
    print("PASS")


if __name__ == "__main__":
    main()
'''


TEMPLATE_README = '''# Web Automation Demo

A Playwright (Python) automation project.

- main.py is the entry point the scheduler runs.
- Add more .py scripts next to it and call them from main.py.
- Run output and artifacts land in the Automation page and ./artifacts.
'''


def scaffold(project: str) -> dict | None:
    """Create a project folder with a working template main.py. Idempotent."""
    base = folder(project)
    if not base.is_dir():
        base.mkdir(parents=True, exist_ok=True)
    main = base / "main.py"
    if not main.is_file():
        main.write_text(TEMPLATE_MAIN, encoding="utf-8")
    readme = base / "README.txt"
    if not readme.is_file():
        readme.write_text(TEMPLATE_README, encoding="utf-8")
    return {"name": safe_project(project), "files": list_files(project)}