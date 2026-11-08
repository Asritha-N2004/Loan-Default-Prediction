"""Local SQLAlchemy snapshots with version lineage, checksums and timestamps."""
import hashlib
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = 'analysis_snapshots'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('analysis_snapshots.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checksum: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)


engine = create_engine(DATABASE_URL, **({'connect_args': {'check_same_thread': False}} if DATABASE_URL.startswith('sqlite') else {}))
if DATABASE_URL.startswith('sqlite'):
    from sqlalchemy import event
    @event.listens_for(engine, 'connect')
    def enable_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
Base.metadata.create_all(engine)


def save(kind: str, payload: dict, parent_id: str | None = None) -> dict:
    canonical = json.dumps(payload, sort_keys=True, allow_nan=False)
    record = Record(id=str(uuid.uuid4()), kind=kind, parent_id=parent_id,
                    created_at=datetime.now(timezone.utc),
                    checksum=hashlib.sha256(canonical.encode()).hexdigest(), payload=json.loads(canonical))
    with Session(engine, expire_on_commit=False) as session:
        session.add(record)
        session.commit()
    return serialize(record)


def serialize(record: Record) -> dict:
    return {'id': record.id, 'kind': record.kind, 'parent_id': record.parent_id,
            'created_at': record.created_at.isoformat(), 'checksum': record.checksum, **record.payload}


def get(record_id: str, kind: str | None = None) -> dict:
    with Session(engine) as session:
        row = session.get(Record, record_id)
        if row is None or (kind and row.kind != kind):
            raise KeyError('Record not found')
        return serialize(row)


def listing(kind: str, offset: int = 0, limit: int = 25) -> list[dict]:
    with Session(engine) as session:
        rows = session.scalars(select(Record).where(Record.kind == kind).order_by(Record.created_at.desc()).offset(offset).limit(limit))
        return [serialize(row) for row in rows]
