"""
DB connection — backend/app/database.py

Connects to Supabase PostgreSQL.
Set the DATABASE_URL env var in backend/.env:

  DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

PostGIS must be enabled on your Supabase project:
  Go to Supabase Dashboard → SQL Editor and run:
    CREATE EXTENSION IF NOT EXISTS postgis;
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env from the backend root (one level up from app/)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    # Fallback to local DB for development without .env
    "postgresql://nithishranjith@localhost:5432/iknos"
)

# Supabase requires sslmode=require on the connection string.
# If the URL doesn't already include it, append it.
if "pooler.supabase.com" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

engine = create_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
