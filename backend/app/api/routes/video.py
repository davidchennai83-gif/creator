from app.api.planned import planned_router
router = planned_router("Video processing", [("GET", ""), ("GET", "/{video_id}"), ("GET", "/{video_id}/status"), ("GET", "/{video_id}/preview"), ("GET", "/{video_id}/download"), ("POST", "/{video_id}/regenerate")])
