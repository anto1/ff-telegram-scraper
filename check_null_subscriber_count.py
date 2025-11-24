"""
Check for channels with null subscriber_count.

This script queries the database and reports how many channels have null subscriber counts.
"""

import asyncio
import os
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def check_null_subscriber_counts():
    """Check for channels with null subscriber_count."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment variables")
        return False
    
    # Convert to async URL if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    print(f"🔌 Connecting to database...")
    
    try:
        # Create async engine
        engine = create_async_engine(database_url, echo=False)
        
        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # Import models
            from models import TelegramChannel
            
            # Count total channels
            total_query = select(func.count()).select_from(TelegramChannel)
            total_result = await session.execute(total_query)
            total_channels = total_result.scalar()
            
            # Count channels with null subscriber_count
            null_query = select(func.count()).select_from(TelegramChannel).where(
                TelegramChannel.subscriber_count.is_(None)
            )
            null_result = await session.execute(null_query)
            null_count = null_result.scalar()
            
            # Count channels with non-null subscriber_count
            not_null_query = select(func.count()).select_from(TelegramChannel).where(
                TelegramChannel.subscriber_count.isnot(None)
            )
            not_null_result = await session.execute(not_null_query)
            not_null_count = not_null_result.scalar()
            
            # Get list of channels with null subscriber_count
            channels_query = select(TelegramChannel).where(
                TelegramChannel.subscriber_count.is_(None)
            )
            channels_result = await session.execute(channels_query)
            channels_with_null = channels_result.scalars().all()
            
            # Display results
            print("\n" + "=" * 70)
            print("📊 SUBSCRIBER COUNT ANALYSIS")
            print("=" * 70)
            print(f"\n📈 Total channels: {total_channels}")
            print(f"✅ Channels with subscriber count: {not_null_count}")
            print(f"❌ Channels with NULL subscriber count: {null_count}")
            
            if null_count > 0:
                percentage = (null_count / total_channels * 100) if total_channels > 0 else 0
                print(f"📊 Percentage with NULL: {percentage:.1f}%")
                
                print(f"\n📋 Channels with NULL subscriber_count:")
                print("-" * 70)
                for channel in channels_with_null:
                    print(f"  ID: {channel.id:4d} | {channel.title[:50]:50s} | @{channel.username or 'N/A'}")
            else:
                print("\n✅ All channels have subscriber counts!")
            
            print("=" * 70)
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("🚀 Checking for channels with null subscriber_count...")
    asyncio.run(check_null_subscriber_counts())

