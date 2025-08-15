"""Database configuration and connection management."""

from sqlalchemy import create_engine
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
def set_sqlite_pragma(dbapi_connection, connection_record):
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