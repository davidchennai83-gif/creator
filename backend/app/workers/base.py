from celery import Celery
from app.config.settings import settings

celery_app = Celery("creator_platform")
from app.workers import celery_config
celery_app.conf.update(celery_config)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_video(self, content_id: str, config: dict):
    """Video generation task"""
    raise NotImplementedError("Video pipeline is not implemented")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def publish_post(self, content_id: str, platform: str, account_id: str, data: dict):
    """Social media publishing task"""
    raise NotImplementedError("Publishing is not implemented")

@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def aggregate_analytics(self, date_range: dict):
    """Analytics aggregation task"""
    raise NotImplementedError("Analytics sync is not implemented")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def send_notification(self, user_id: str, notification_data: dict):
    """Notification task"""
    raise NotImplementedError("Notification delivery is not implemented")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def track_affiliate(self, click_data: dict):
    """Affiliate tracking task"""
    raise NotImplementedError("Affiliate tracking is not implemented")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_order(self, order_id: str):
    """Order processing task"""
    raise NotImplementedError("Commerce is not implemented")

@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_content_ai(self, prompt: dict):
    """AI content generation task"""
    from app.utils import get_ai_provider
    from dataclasses import asdict
    return asdict(get_ai_provider().generate(prompt["prompt"]))
