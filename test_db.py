import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
if "asyncpg" in DATABASE_URL:
    if "?" in DATABASE_URL:
        DATABASE_URL += "&prepared_statement_cache_size=0"
    else:
        DATABASE_URL += "?prepared_statement_cache_size=0"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False, 
    pool_pre_ping=True, 
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0}
)

async def test():
    async with engine.connect() as conn:
        print("Connected successfully!")
        
asyncio.run(test())
