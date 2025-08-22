"""Database configuration and connection management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
from sqlalchemy import event
from config import settings
from app.models.profile import Base


def _get_default_sqlite_url() -> str:
    """Default to local SQLite DB if DATABASE_URL not explicitly set."""
    default_path = "/Users/pedroarruda/Desktop/one/o1_visa_profiles.db"
    return f"sqlite:///{default_path}"


database_url = settings.database_url or _get_default_sqlite_url()

# Create database engine
engine = create_engine(
    database_url,
    connect_args=(
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    ),
)

# Enable SQLite foreign keys
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _):
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _ensure_profile_judge_columns()


def _ensure_profile_judge_columns():
    """Ensure new judge-related columns exist on profiles (SQLite-safe)."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info('profiles')"))
            cols = {row[1] for row in res.fetchall()}
            alter_cmds = []
            if 'judge_status' not in cols:
                alter_cmds.append("ALTER TABLE profiles ADD COLUMN judge_status TEXT DEFAULT 'unknown'")
            if 'judge_notes' not in cols:
                alter_cmds.append("ALTER TABLE profiles ADD COLUMN judge_notes TEXT")
            if 'judge_auto_score' not in cols:
                alter_cmds.append("ALTER TABLE profiles ADD COLUMN judge_auto_score REAL")
            if 'judge_auto_reason' not in cols:
                alter_cmds.append("ALTER TABLE profiles ADD COLUMN judge_auto_reason TEXT")
            if 'review_status' not in cols:
                alter_cmds.append("ALTER TABLE profiles ADD COLUMN review_status TEXT DEFAULT 'under_review'")
            for cmd in alter_cmds:
                conn.execute(text(cmd))
    except Exception:
        # fail-safe: don't crash app on migration errors
        pass