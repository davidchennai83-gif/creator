from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from app.api.deps import editor, get_current_user
from app.automation import store as automation_store
from app.schemas.common import success
from app.video_creator import schedules

router = APIRouter()


@router.get('/projects')
def projects(user=Depends(get_current_user)):
    video = [{'id': p['id'], 'name': p['name'], 'description': p['description'], 'kind': 'video'}
             for p in schedules.PROJECTS]
    automation = [{'id': schedules.AUTOMATION_PREFIX + p['name'], 'name': p['name'],
                   'description': f'Playwright automation · {len(p["files"])} script file(s)',
                   'kind': 'automation', 'files': p['files']}
                  for p in automation_store.list_projects()]
    return success(video + automation)


@router.get('')
def listing(user=Depends(get_current_user)):
    return success(schedules.listing(user.id))


def attempt(call):
    try:
        return success(call())
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post('', status_code=201)
def create(data: schedules.ScheduleInput, user=Depends(editor)):
    return attempt(lambda: schedules.put(user.id, data))


@router.put('/{task_id}')
def update(task_id: UUID, data: schedules.ScheduleInput, user=Depends(editor)):
    return attempt(lambda: schedules.put(user.id, data, task_id))


@router.post('/{task_id}/pause')
def pause(task_id: UUID, user=Depends(editor)):
    return attempt(lambda: schedules.change(user.id, task_id, 'pause'))


@router.post('/{task_id}/resume')
def resume(task_id: UUID, user=Depends(editor)):
    return attempt(lambda: schedules.change(user.id, task_id, 'resume'))


@router.delete('/{task_id}')
def delete(task_id: UUID, user=Depends(editor)):
    return attempt(lambda: schedules.change(user.id, task_id, 'delete'))
