import secrets
from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def migrate_db():
    """Apply lightweight schema migrations that SQLModel cannot handle automatically."""
    with engine.begin() as conn:
        # C1: add webhook_token to integrations (idempotent)
        try:
            conn.execute(text("ALTER TABLE integrations ADD COLUMN webhook_token TEXT"))
        except Exception:
            pass  # column already exists
        # Populate any rows that still have NULL webhook_token
        rows = conn.execute(
            text("SELECT id FROM integrations WHERE webhook_token IS NULL")
        ).fetchall()
        for (row_id,) in rows:
            token = secrets.token_urlsafe(32)
            conn.execute(
                text("UPDATE integrations SET webhook_token = :t WHERE id = :id"),
                {"t": token, "id": row_id},
            )


def get_session():
    with Session(engine) as session:
        yield session
