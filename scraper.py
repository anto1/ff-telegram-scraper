"""
Telegram channel scraper with database integration.

Refactored from parser.py to use PostgreSQL database instead of hardcoded channels.
Reads active channels from DB, scrapes messages, and saves results to DB.
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv
from telethon import TelegramClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import AsyncSessionLocal
from models import TelegramChannel, TelegramMessage

# Load environment variables
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Initialize Telegram client
client = TelegramClient("telegram_session", API_ID, API_HASH)


# ============================================================================
# METRICS CALCULATION (from original parser.py)
# ============================================================================

def get_total_reactions(message):
    """
    Calculate total reaction count for a message, excluding paid reactions.
    
    Only counts free reactions (ReactionEmoji) to measure genuine organic engagement.
    Excludes ReactionPaid and ReactionCustomEmoji (Telegram Stars).
    
    Args:
        message: Telegram message object
        
    Returns:
        int: Total count of free reactions
    """
    if not message.reactions:
        return 0
    
    results = getattr(message.reactions, "results", None)
    if not results:
        return 0
    
    total_free = 0
    
    for r in results:
        reaction = getattr(r, "reaction", None)
        count = getattr(r, "count", 0) or 0
        
        if not reaction:
            # No reaction object, count as free (backward compatibility)
            total_free += count
            continue
        
        # Check reaction type
        reaction_type = type(reaction).__name__
        
        if reaction_type in ("ReactionPaid", "ReactionCustomEmoji"):
            # Skip paid reactions
            continue
        else:
            # Free reaction (ReactionEmoji or other types)
            total_free += count
    
    return total_free


def calculate_engagement(message, total_reactions: int) -> dict:
    """
    Calculate engagement metrics for a message.
    
    Engagement = reactions + forwards + replies
    Engagement rate = (engagement / views) * 100
    
    Args:
        message: Telegram message object
        total_reactions: Pre-calculated total reaction count
        
    Returns:
        dict: {"engagement_count": int, "engagement_rate": float}
    """
    views = message.views or 0
    forwards = message.forwards or 0
    replies = getattr(message.replies, "replies", None) if message.replies else 0
    replies = replies or 0
    
    engagement_count = total_reactions + forwards + replies
    engagement_rate = (engagement_count / views * 100) if views > 0 else 0
    
    return {
        "engagement_count": engagement_count,
        "engagement_rate": round(engagement_rate, 4)
    }


# ============================================================================
# DATABASE-INTEGRATED SCRAPING FUNCTIONS
# ============================================================================

async def get_active_channels(db: AsyncSession) -> List[TelegramChannel]:
    """
    Fetch all active channels from database.
    
    Args:
        db: Database session
        
    Returns:
        List of active TelegramChannel objects
    """
    query = select(TelegramChannel).where(TelegramChannel.is_active == True)
    result = await db.execute(query)
    channels = result.scalars().all()
    return list(channels)


async def scrape_channel(
    channel: TelegramChannel,
    db: AsyncSession,
    limit: int = 200
) -> dict:
    """
    Scrape a single Telegram channel and save messages to database.
    
    Args:
        channel: TelegramChannel object from database
        db: Database session
        limit: Maximum number of messages to fetch
        
    Returns:
        dict: {"success": bool, "messages_scraped": int, "error": str or None}
    """
    try:
        print(f"📡 Scraping channel: {channel.title} (ID: {channel.channel_id})")
        
        messages_scraped = 0
        messages_updated = 0
        
        # Fetch messages from Telegram
        async for message in client.iter_messages(channel.channel_id, limit=limit):
            # Calculate metrics
            total_reactions = get_total_reactions(message)
            engagement = calculate_engagement(message, total_reactions)
            post_length = len(message.text) if message.text else 0
            
            # Check if message already exists (by channel_id + message_id)
            existing_query = select(TelegramMessage).where(
                TelegramMessage.channel_id == channel.id,
                TelegramMessage.message_id == message.id
            )
            existing_result = await db.execute(existing_query)
            existing_message = existing_result.scalar_one_or_none()
            
            if existing_message:
                # Update existing message (metrics may have changed)
                existing_message.views = message.views
                existing_message.forwards = message.forwards
                existing_message.replies = getattr(message.replies, "replies", None) if message.replies else None
                existing_message.total_reactions = total_reactions
                existing_message.engagement_count = engagement["engagement_count"]
                existing_message.engagement_rate = engagement["engagement_rate"]
                existing_message.post_length = post_length
                messages_updated += 1
            else:
                # Create new message
                new_message = TelegramMessage(
                    channel_id=channel.id,
                    message_id=message.id,
                    date=message.date,
                    text=message.text,
                    views=message.views,
                    forwards=message.forwards,
                    replies=getattr(message.replies, "replies", None) if message.replies else None,
                    total_reactions=total_reactions,
                    engagement_count=engagement["engagement_count"],
                    engagement_rate=engagement["engagement_rate"],
                    post_length=post_length,
                    # raw_json could be added here if needed: raw_json=message.to_dict()
                )
                db.add(new_message)
                messages_scraped += 1
        
        # Update last_scraped_at timestamp
        channel.last_scraped_at = datetime.now(timezone.utc)
        
        # Commit all changes
        await db.commit()
        
        print(f"✓ {channel.title}: {messages_scraped} new, {messages_updated} updated")
        
        return {
            "success": True,
            "messages_scraped": messages_scraped,
            "messages_updated": messages_updated,
            "error": None
        }
        
    except Exception as e:
        print(f"✗ Error scraping {channel.title}: {str(e)}")
        await db.rollback()
        
        return {
            "success": False,
            "messages_scraped": 0,
            "messages_updated": 0,
            "error": str(e)
        }


async def scrape_all_active_channels(db: AsyncSession, limit: int = 200) -> dict:
    """
    Scrape all active channels from database.
    
    This is the main entry point for scraping. It:
    1. Fetches all active channels from DB
    2. Connects to Telegram
    3. Scrapes each channel
    4. Saves results to DB
    
    Args:
        db: Database session
        limit: Maximum messages to fetch per channel
        
    Returns:
        dict: Summary statistics of scraping operation
    """
    started_at = datetime.now(timezone.utc)
    
    # Get active channels
    channels = await get_active_channels(db)
    
    if not channels:
        print("⚠️  No active channels found in database")
        return {
            "success": False,
            "channels_processed": 0,
            "total_messages_scraped": 0,
            "total_messages_updated": 0,
            "errors": ["No active channels found"],
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc)
        }
    
    print(f"\n🚀 Starting scrape of {len(channels)} channels...")
    print("="*80)
    
    total_scraped = 0
    total_updated = 0
    errors = []
    
    # Ensure Telegram client is connected
    if not client.is_connected():
        await client.connect()
    
    # Scrape each channel
    for channel in channels:
        result = await scrape_channel(channel, db, limit=limit)
        
        if result["success"]:
            total_scraped += result["messages_scraped"]
            total_updated += result["messages_updated"]
        else:
            errors.append(f"{channel.title}: {result['error']}")
    
    completed_at = datetime.now(timezone.utc)
    duration = (completed_at - started_at).total_seconds()
    
    print("="*80)
    print(f"✓ Scraping completed in {duration:.2f} seconds")
    print(f"  Channels processed: {len(channels)}")
    print(f"  New messages: {total_scraped}")
    print(f"  Updated messages: {total_updated}")
    if errors:
        print(f"  Errors: {len(errors)}")
    print()
    
    return {
        "success": len(errors) == 0,
        "channels_processed": len(channels),
        "total_messages_scraped": total_scraped,
        "total_messages_updated": total_updated,
        "errors": errors,
        "started_at": started_at,
        "completed_at": completed_at
    }


async def scrape_specific_channels(db: AsyncSession, channel_ids: List[int], limit: int = 200) -> dict:
    """
    Scrape specific channels by their database IDs.
    
    Args:
        db: Database session
        channel_ids: List of channel database IDs to scrape
        limit: Maximum messages to fetch per channel
        
    Returns:
        dict: Summary statistics of scraping operation
    """
    started_at = datetime.now(timezone.utc)
    
    # Get specified channels
    query = select(TelegramChannel).where(
        TelegramChannel.id.in_(channel_ids),
        TelegramChannel.is_active == True
    )
    result = await db.execute(query)
    channels = result.scalars().all()
    
    if not channels:
        return {
            "success": False,
            "channels_processed": 0,
            "total_messages_scraped": 0,
            "total_messages_updated": 0,
            "errors": ["No matching active channels found"],
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc)
        }
    
    print(f"\n🚀 Starting scrape of {len(channels)} specified channels...")
    
    # Ensure Telegram client is connected
    if not client.is_connected():
        await client.connect()
    
    total_scraped = 0
    total_updated = 0
    errors = []
    
    for channel in channels:
        result = await scrape_channel(channel, db, limit=limit)
        
        if result["success"]:
            total_scraped += result["messages_scraped"]
            total_updated += result["messages_updated"]
        else:
            errors.append(f"{channel.title}: {result['error']}")
    
    completed_at = datetime.now(timezone.utc)
    
    return {
        "success": len(errors) == 0,
        "channels_processed": len(channels),
        "total_messages_scraped": total_scraped,
        "total_messages_updated": total_updated,
        "errors": errors,
        "started_at": started_at,
        "completed_at": completed_at
    }


# ============================================================================
# MAIN CLI ENTRY POINT
# ============================================================================

async def main():
    """
    Main function for running scraper from command line.
    
    Usage:
        python scraper.py
    """
    print("="*80)
    print("TELEGRAM CHANNEL SCRAPER")
    print("="*80)
    print()
    
    # Connect to Telegram
    await client.start()
    me = await client.get_me()
    print(f"🔐 Logged in as: {me.username or me.first_name}")
    print()
    
    # Run scraping
    result = await scrape_all_active_channels(limit=200)
    
    # Print summary
    if result["success"]:
        print("✅ Scraping completed successfully!")
    else:
        print("⚠️  Scraping completed with errors:")
        for error in result["errors"]:
            print(f"  - {error}")
    
    return result


if __name__ == "__main__":
    """
    Run scraper as standalone script.
    
    This connects to Telegram, fetches active channels from database,
    scrapes messages, and saves to database.
    
    Requirements:
    - Database must be running and accessible via DATABASE_URL
    - Telegram credentials in .env (API_ID, API_HASH)
    - telegram_session.session file (created on first run)
    """
    
    with client:
        result = client.loop.run_until_complete(main())

