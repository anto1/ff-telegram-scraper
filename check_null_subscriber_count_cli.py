"""
Check for channels with null subscriber_count.

This script queries the database and reports how many channels have null subscriber counts.

Usage:
    python3 check_null_subscriber_count_cli.py <DATABASE_URL>
    
Example:
    python3 check_null_subscriber_count_cli.py "postgresql://user:pass@host:port/dbname"
"""

import asyncio
import sys
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def check_null_subscriber_counts(database_url):
    """Check for channels with null subscriber_count."""
    
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
            ).limit(100)  # Limit to first 100 for display
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
                
                print(f"\n📋 Channels with NULL subscriber_count (showing first {len(channels_with_null)}):")
                print("-" * 70)
                for channel in channels_with_null:
                    username_str = f"@{channel.username}" if channel.username else "N/A"
                    print(f"  ID: {channel.id:4d} | {channel.title[:40]:40s} | {username_str:20s}")
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
    if len(sys.argv) < 2:
        print("❌ ERROR: Please provide DATABASE_URL as argument")
        print("\nUsage:")
        print("  python3 check_null_subscriber_count_cli.py <DATABASE_URL>")
        print("\nExample:")
        print('  python3 check_null_subscriber_count_cli.py "postgresql://user:pass@host:port/dbname"')
        sys.exit(1)
    
    database_url = sys.argv[1]
    print(f"🚀 Checking for channels with null subscriber_count...")
    success = asyncio.run(check_null_subscriber_counts(database_url))
    
    sys.exit(0 if success else 1)

