from app.config.settings import settings

celery_config = {
    "broker_url": settings.CELERY_BROKER_URL,
    "result_backend": settings.CELERY_RESULT_BACKEND,
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "task_soft_time_limit": 600,
    "task_time_limit": 660,
    "result_expires": 86400,
    "broker_connection_retry_on_startup": True,
    "task_routes": {
        f"app.workers.base.{task}": {"queue": queue}
        for task, queue in {
            "generate_video": "video_queue", "publish_post": "publishing_queue",
            "aggregate_analytics": "analytics_queue", "send_notification": "notification_queue",
            "track_affiliate": "affiliate_queue", "process_order": "commerce_queue",
            "generate_content_ai": "ai_queue",
        }.items()
    },
}
