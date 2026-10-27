"""Playwright automation projects: store, edit, run, and inspect runs."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import editor
from app.automation import runner, store
from app.schemas.common import success

router = APIRouter()


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class SaveFile(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = ""


class RunProject(BaseModel):
    file: str = Field(default="main.py", max_length=120)


def attempt(call):
    try:
        return success(call())
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.get("/projects")
def projects(user=Depends(editor)):
    return success(store.list_projects())


@router.get("/projects/{project}/files/{file}")
def read_file(project: str, file: str, user=Depends(editor)):
    try:
        found = store.read(project, file)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not found:
        raise HTTPException(404, "File not found")
    return success(found)


@router.post("/projects", status_code=201)
def create(data: CreateProject, user=Depends(editor)):
    return attempt(lambda: store.scaffold(data.name))


@router.post("/projects/{project}/files")
def save_file(project: str, data: SaveFile, user=Depends(editor)):
    return attempt(lambda: success({"name": store.write(project, data.name, data.content)}))


@router.delete("/projects/{project}/files/{file}")
def delete_file(project: str, file: str, user=Depends(editor)):
    try:
        deleted = store.delete_file(project, file)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not deleted:
        raise HTTPException(404, "File not found")
    return success({"deleted": store.safe_file(file)})


@router.delete("/projects/{project}")
def remove_project(project: str, user=Depends(editor)):
    try:
        removed = store.delete_project(project)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not removed:
        raise HTTPException(404, "Project not found")
    return success({"deleted": True})


@router.post("/projects/{project}/run", status_code=202)
def run_project(project: str, data: RunProject, user=Depends(editor)):
    return attempt(lambda: runner.run(user.id, project, data.file))


@router.get("/runs")
def runs(user=Depends(editor)):
    return success(runner.listing(user.id))


@router.get("/files/{project}")
def list_project_files(project: str, user=Depends(editor)):
    return attempt(lambda: success({"files": store.list_files(project)}))


# Log/diagnostic download for a completed run.
@router.get("/runs/{run_id}/log")
def run_log(run_id: str, user=Depends(editor)):
    from fastapi.responses import FileResponse

    run = runner.get(run_id, user.id)
    if not run:
        raise HTTPException(404, "Run not found")
    path = Path(run.get("log_file") or "")
    if not path.is_file():
        return success({"preview": run.get("preview", "")})
    return FileResponse(path, media_type="text/plain", filename=f"{run_id}.log")