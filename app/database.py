import os
import asyncio
from databases import Database
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

database = Database(DATABASE_URL, statement_cache_size=0, min_size=1, max_size=10)


async def connect_to_db():
    max_retries = 3
    retry_delay = 2

    for attempt in range(1, max_retries + 1):
        try:
            await database.connect()
            print(f"✅ Database connected to Supabase (attempt {attempt})")
            return
        except Exception as e:
            print(f"⚠️ DB connection failed ({attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

    print("❌ Database unavailable. Check Supabase credentials or SSL.")


async def close_db_connection():
    if database.is_connected:
        await database.disconnect()
        print("🛑 Database disconnected")
