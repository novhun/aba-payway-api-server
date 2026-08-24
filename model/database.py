import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

load_dotenv()

raw_db_url = os.getenv("DATABASE_URL", "").strip()
if not raw_db_url:
    DATABASE_URL = "sqlite+aiosqlite:///aba_automation.db"
else:
    DATABASE_URL = raw_db_url

API_KEY = os.getenv("API_KEY", "your_super_secret_api_key_here")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")

engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}

if "asyncpg" in DATABASE_URL:
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?prepared_statement_cache_size=0"
    elif "prepared_statement_cache_size=0" not in DATABASE_URL:
        DATABASE_URL += "&prepared_statement_cache_size=0"
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["connect_args"] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
elif "sqlite" in DATABASE_URL:
    engine_kwargs["connect_args"] = {
        "check_same_thread": False,
    }
else:
    # MySQL / Other databases
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(DATABASE_URL, **engine_kwargs)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()
