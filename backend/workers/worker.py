# Worker startup script
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workers.base import celery_app

if __name__ == "__main__":
    args = ["worker", "--loglevel=info", "-Q", "video_queue,publishing_queue,analytics_queue,notification_queue,affiliate_queue,commerce_queue,ai_queue"]
    if sys.platform == "win32":
        args.extend(["--pool=solo", "--concurrency=1"])
    celery_app.worker_main(args)
