"""
Database configuration and session management.

Provides async SQLAlchemy engine and session factory for use with FastAPI.
Uses connection pooling optimized for Railway's Postgres.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
# Railway provides DATABASE_URL, but it uses postgres:// scheme
# asyncpg requires postgresql:// scheme, so we need to replace it
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/telegram_scraper")

# Fix Railway's postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    # Replace with asyncpg driver
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
# echo=True for development (logs all SQL queries)
# pool_pre_ping=True ensures connections are alive before using them
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query debugging
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for all models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI routes to get database session.
    
    Usage in FastAPI:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            # use db here
            pass
    
    Yields:
        AsyncSession: Database session that auto-closes after request
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Initialize database - create all tables if they don't exist.
    
    This is a simple approach for initial setup. For production,
    consider using Alembic migrations for better control.
    
    Call this on application startup.
    """
    async with engine.begin() as conn:
        # Import models to ensure they're registered
        from models import TelegramChannel, TelegramMessage
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✓ Database tables created/verified")

