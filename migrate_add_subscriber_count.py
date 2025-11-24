"""
Database migration: Add subscriber_count column to telegram_channels table.

This migration adds the subscriber_count field to existing channels.
Run this script once after deploying the updated code to Railway.

Usage:
    python3 migrate_add_subscriber_count.py
"""

import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def run_migration():
    """Add subscriber_count column to telegram_channels table."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        return False
    
    # Convert to async URL if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"🔌 Connecting to database...")
    
    try:
        # Create async engine
        engine = create_async_engine(database_url, echo=True)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            print("📝 Checking if subscriber_count column exists...")
            
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='telegram_channels' 
                AND column_name='subscriber_count';
            """)
            
            result = await session.execute(check_query)
            exists = result.fetchone()
            
            if exists:
                print("✓ subscriber_count column already exists. No migration needed.")
                return True
            
            print("➕ Adding subscriber_count column...")
            
            # Add the column
            alter_query = text("""
                ALTER TABLE telegram_channels 
                ADD COLUMN subscriber_count INTEGER DEFAULT NULL;
            """)
            
            await session.execute(alter_query)
            await session.commit()
            
            print("✅ Migration completed successfully!")
            print("   - Added subscriber_count column to telegram_channels table")
            
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("🚀 Starting database migration...")
    print("=" * 60)
    
    success = asyncio.run(run_migration())
    
    print("=" * 60)
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed. Please check the errors above.")



