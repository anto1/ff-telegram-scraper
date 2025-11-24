"""
Fix NULL subscriber_count values by fetching from Telegram.

This script:
1. Finds all channels with NULL subscriber_count
2. Connects to Telegram
3. Fetches the actual subscriber count for each channel
4. Updates the database with the real values

Usage:
    python3 fix_null_subscriber_counts.py
"""

import asyncio
import os
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def fix_null_subscriber_counts():
    """Fetch and update subscriber counts for channels with NULL values."""
    
    # Import here to avoid circular imports
    from db import AsyncSessionLocal, init_db
    from models import TelegramChannel
    from scraper import client as telegram_client
    
    logger.info("🚀 Starting subscriber count fix...")
    logger.info("=" * 70)
    
    # Initialize database
    await init_db()
    
    try:
        # Connect to Telegram
        if not telegram_client.is_connected():
            logger.info("📡 Connecting to Telegram...")
            await telegram_client.connect()
            logger.info("✅ Connected to Telegram")
        
        # Get database session
        async with AsyncSessionLocal() as db:
            # Find all channels with NULL subscriber_count
            query = select(TelegramChannel).where(
                TelegramChannel.subscriber_count.is_(None)
            )
            result = await db.execute(query)
            channels = result.scalars().all()
            
            total_channels = len(channels)
            logger.info(f"\n📊 Found {total_channels} channels with NULL subscriber_count")
            
            if total_channels == 0:
                logger.info("✅ All channels already have subscriber counts!")
                return
            
            logger.info(f"\n🔄 Processing channels...")
            logger.info("-" * 70)
            
            updated_count = 0
            failed_count = 0
            
            for i, channel in enumerate(channels, 1):
                try:
                    logger.info(f"\n[{i}/{total_channels}] Processing: {channel.title}")
                    
                    # Try to get the channel entity from Telegram
                    try:
                        # Try by username first if available
                        if channel.username and channel.username != "no_username":
                            telegram_entity = await telegram_client.get_entity(channel.username)
                        else:
                            # Try by channel_id
                            telegram_entity = await telegram_client.get_entity(channel.channel_id)
                        
                        # Get FULL channel info to access participants_count
                        # Regular get_entity() doesn't include this information
                        from telethon.tl.functions.channels import GetFullChannelRequest
                        full_channel = await telegram_client(GetFullChannelRequest(channel=telegram_entity))
                        
                        # Get subscriber count from full channel info
                        subscriber_count = full_channel.full_chat.participants_count
                        
                        if subscriber_count is not None:
                            # Update the database
                            channel.subscriber_count = subscriber_count
                            await db.commit()
                            await db.refresh(channel)
                            
                            logger.info(f"  ✅ Updated: {subscriber_count:,} subscribers")
                            updated_count += 1
                        else:
                            logger.warning(f"  ⚠️  Could not get subscriber count (might be a private channel)")
                            failed_count += 1
                    
                    except ValueError as e:
                        logger.warning(f"  ⚠️  Could not find channel: {e}")
                        failed_count += 1
                    except Exception as e:
                        logger.error(f"  ❌ Error fetching channel: {e}")
                        failed_count += 1
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)
                
                except Exception as e:
                    logger.error(f"  ❌ Unexpected error: {e}")
                    failed_count += 1
                    await db.rollback()
            
            # Final summary
            logger.info("\n" + "=" * 70)
            logger.info("📊 SUMMARY")
            logger.info("=" * 70)
            logger.info(f"Total channels processed: {total_channels}")
            logger.info(f"✅ Successfully updated: {updated_count}")
            logger.info(f"❌ Failed: {failed_count}")
            logger.info("=" * 70)
            
            if updated_count > 0:
                logger.info(f"\n✅ Successfully updated {updated_count} channel(s)!")
            
            if failed_count > 0:
                logger.info(f"\n⚠️  {failed_count} channel(s) could not be updated.")
                logger.info("   This is normal for private channels or channels you're no longer subscribed to.")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Disconnect from Telegram
        if telegram_client.is_connected():
            await telegram_client.disconnect()
            logger.info("\n🔌 Disconnected from Telegram")
    
    return True


if __name__ == "__main__":
    print("🔧 Fixing NULL subscriber counts...")
    print("=" * 70)
    
    try:
        success = asyncio.run(fix_null_subscriber_counts())
        if success:
            print("\n✅ Fix completed!")
        else:
            print("\n❌ Fix failed. Please check the errors above.")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

