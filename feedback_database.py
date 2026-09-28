import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import SessionLocal, engine


load_dotenv()

FEEDBACK_DATABASE_URL = os.getenv("FEEDBACK_DATABASE_URL")

if FEEDBACK_DATABASE_URL:
    if FEEDBACK_DATABASE_URL.startswith("postgres://"):
        FEEDBACK_DATABASE_URL = FEEDBACK_DATABASE_URL.replace(
            "postgres://", "postgresql://", 1
        )

    feedback_connect_args = (
        {"check_same_thread": False}
        if FEEDBACK_DATABASE_URL.startswith("sqlite")
        else {}
    )
    feedback_engine = create_engine(
        FEEDBACK_DATABASE_URL,
        connect_args=feedback_connect_args,
        pool_pre_ping=True,
    )
    FeedbackSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=feedback_engine,
    )
else:
    feedback_engine = engine
    FeedbackSessionLocal = SessionLocal


def criar_tabela_feedback():
    from model.models import FeedbackAtendimento

    FeedbackAtendimento.__table__.create(bind=feedback_engine, checkfirst=True)


def get_feedback_db():
    db = FeedbackSessionLocal()
    try:
        yield db
    finally:
        db.close()
