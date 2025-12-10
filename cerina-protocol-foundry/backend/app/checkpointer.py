# backend/app/checkpointer.py
from sqlmodel import Session, create_engine, select, SQLModel
from .models.db_models import RunCheckpoint
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

def init_db():
    SQLModel.metadata.create_all(engine)

def save_checkpoint(run_id: str, agent_name: str, state: dict, note: str = None):
    with Session(engine) as session:
        cp = RunCheckpoint(run_id=run_id, agent_name=agent_name, state_snapshot=state, note=note)
        session.add(cp)
        session.commit()
        session.refresh(cp)
        return cp

def load_last_checkpoint(run_id: str):
    with Session(engine) as session:
        stmt = select(RunCheckpoint).where(RunCheckpoint.run_id == run_id).order_by(RunCheckpoint.timestamp.desc())
        res = session.exec(stmt).first()
        return res

def list_checkpoints(run_id: str):
    with Session(engine) as session:
        stmt = select(RunCheckpoint).where(RunCheckpoint.run_id == run_id).order_by(RunCheckpoint.timestamp.asc())
        return session.exec(stmt).all()