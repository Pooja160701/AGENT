# backend/app/models/db_models.py
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON
from datetime import datetime
import uuid

class RunCheckpoint(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    run_id: str
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    # Use an actual SQLAlchemy Column with JSON type for compatibility
    state_snapshot: dict = Field(sa_column=Column(JSON), default={})
    note: Optional[str] = None