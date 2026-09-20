# Celery Beat scheduler script
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workers.base import celery_app

if __name__ == "__main__":
    celery_app.start(["celery", "beat", "--loglevel=info"])
