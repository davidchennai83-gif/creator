from sqlalchemy import Column, Integer, String, Date, Text, JSON
from app.main import Base


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True)  # e.g., "1947-08-15"
    event_title = Column(String(200), nullable=False)  # e.g., "India Independence"
    event_description = Column(Text, nullable=False)   # Full description in English
    tamil_title = Column(String(200), nullable=False)  # Tamil translation
    tamil_description = Column(Text, nullable=False)   # Tamil description
    importance_points = Column(JSON, nullable=False)   # 10 key points as JSON array
    bgm_track = Column(String(100))                    # BGM filename
    voice_over_path = Column(String(100))              # Audio file path