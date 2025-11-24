"""
Database configuration and session management.

Provides async SQLAlchemy engine and session factory for use with FastAPI.
Uses connection pooling optimized for Railway's Postgres.

Note: Automatically converts postgres:// and postgresql:// URLs to postgresql+asyncpg://
"""

import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database URL from environment
# Railway provides DATABASE_URL, but it uses postgres:// scheme
# asyncpg requires postgresql:// scheme, so we need to replace it
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("❌ DATABASE_URL environment variable is not set!")
    logger.error("Please set DATABASE_URL in your Railway environment variables.")
    logger.error("It should look like: postgresql+asyncpg://user:pass@host:port/dbname")
    raise ValueError("DATABASE_URL environment variable not set")

logger.info(f"📡 DATABASE_URL found: {DATABASE_URL[:30]}...")

# Fix Railway's postgres:// to postgresql://
original_url = DATABASE_URL
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    logger.info("🔧 Converted postgres:// to postgresql+asyncpg://")
elif DATABASE_URL.startswith("postgresql://"):
    # Replace with asyncpg driver
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("🔧 Converted postgresql:// to postgresql+asyncpg://")
elif not DATABASE_URL.startswith("postgresql+asyncpg://"):
    logger.warning(f"⚠️  DATABASE_URL has unexpected scheme: {DATABASE_URL[:30]}...")

# Log connection details (without password)
try:
    if "@" in DATABASE_URL:
        host_part = DATABASE_URL.split("@")[1]
        logger.info(f"🔌 Attempting to connect to: {host_part}")
    else:
        logger.info(f"🔌 Attempting to connect with URL format: {DATABASE_URL[:50]}...")
except Exception as e:
    logger.warning(f"⚠️  Could not parse DATABASE_URL for logging: {e}")

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
    try:
        logger.info("🗄️  Initializing database...")
        async with engine.begin() as conn:
            # Import models to ensure they're registered
            from models import TelegramChannel, TelegramMessage
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created/verified successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        logger.error("Please check:")
        logger.error("  1. DATABASE_URL is set correctly in Railway")
        logger.error("  2. PostgreSQL service is running")
        logger.error("  3. Network access between services is allowed")
        raise

