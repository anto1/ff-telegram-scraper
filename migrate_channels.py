"""
Migration helper script to import channels from parser.py into database.

This script helps you transition from the old hardcoded channel list
to the new database-driven approach.

Usage:
    python migrate_channels.py
"""

import asyncio
from sqlalchemy import select
from db import AsyncSessionLocal
from models import TelegramChannel
from datetime import datetime


# Add your existing channels here
# You can get these from your old parser.py CHANNELS dict or from Telegram
CHANNELS_TO_IMPORT = [
    # Format: (title, channel_id, username (optional), notes (optional))
    
    # Example channels - replace with your actual channels
    ("Pokerok", -1001213573012, "pokerok", "Official Pokerok channel"),
    ("Posidelki s Shakhovtsom", -1001418874148, "posidelki_s_shakhovtsom", None),
    ("A-Game Poker", -1001868304845, "a_game", None),
    ("Что на ривере", -1001207505171, "chto_na_rivere", None),
    ("SPR Poker", -1001469944207, "spr_poker", None),
    ("Misha Inner", -1001455436304, "misha_inner", None),
    
    # Add more channels here...
    # You can also discover channels using the discover_channels() function below
]


async def import_channels():
    """Import channels from CHANNELS_TO_IMPORT list into database."""
    async with AsyncSessionLocal() as db:
        imported = 0
        skipped = 0
        errors = 0
        
        print("\n" + "="*80)
        print("CHANNEL MIGRATION SCRIPT")
        print("="*80)
        print(f"\nFound {len(CHANNELS_TO_IMPORT)} channels to import")
        print()
        
        for channel_data in CHANNELS_TO_IMPORT:
            # Unpack channel data
            if len(channel_data) == 2:
                title, channel_id = channel_data
                username = None
                notes = None
            elif len(channel_data) == 3:
                title, channel_id, username = channel_data
                notes = None
            else:
                title, channel_id, username, notes = channel_data
            
            try:
                # Check if channel already exists
                existing = await db.execute(
                    select(TelegramChannel).where(
                        TelegramChannel.channel_id == channel_id
                    )
                )
                
                if existing.scalar_one_or_none():
                    print(f"⊘ Skipped: {title} (already exists)")
                    skipped += 1
                    continue
                
                # Create new channel
                new_channel = TelegramChannel(
                    title=title,
                    channel_id=channel_id,
                    username=username,
                    is_active=True,  # Set to True by default
                    notes=notes,
                )
                
                db.add(new_channel)
                await db.commit()
                
                print(f"✓ Imported: {title} (ID: {channel_id})")
                imported += 1
                
            except Exception as e:
                print(f"✗ Error importing {title}: {str(e)}")
                errors += 1
                await db.rollback()
        
        print()
        print("="*80)
        print("MIGRATION SUMMARY")
        print("="*80)
        print(f"Imported: {imported}")
        print(f"Skipped:  {skipped}")
        print(f"Errors:   {errors}")
        print()
        
        if imported > 0:
            print("✅ Channels successfully imported to database!")
            print("   You can now run 'python scraper.py' to start scraping.")
        elif skipped > 0 and imported == 0:
            print("ℹ️  All channels already exist in database.")
        
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        }


async def discover_channels():
    """
    Discover all subscribed Telegram channels and print them.
    
    Use this to find channel IDs if you don't know them.
    This requires Telegram authentication.
    """
    from telethon import TelegramClient
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    
    client = TelegramClient("telegram_session", API_ID, API_HASH)
    
    print("\n" + "="*80)
    print("TELEGRAM CHANNEL DISCOVERY")
    print("="*80)
    print("\nConnecting to Telegram...\n")
    
    await client.start()
    
    channels = []
    
    async for dialog in client.iter_dialogs():
        # Only channels (not groups or private chats)
        if dialog.is_channel and not dialog.is_group:
            channels.append({
                "title": dialog.name,
                "id": dialog.id,
                "username": dialog.entity.username if hasattr(dialog.entity, 'username') else None,
            })
    
    print(f"Found {len(channels)} channels:\n")
    print("-"*80)
    
    for channel in channels:
        username = f"@{channel['username']}" if channel['username'] else "No username"
        print(f"{channel['title']:<40} | {channel['id']:>15} | {username}")
    
    print("-"*80)
    print("\nTo import these channels, copy them to CHANNELS_TO_IMPORT in this script:")
    print("Format: (\"Title\", channel_id, \"username\", \"notes\")\n")
    
    for channel in channels:
        username = f'"{channel["username"]}"' if channel["username"] else "None"
        print(f'    ("{channel["title"]}", {channel["id"]}, {username}, None),')
    
    print()
    
    await client.disconnect()


async def list_database_channels():
    """List all channels currently in the database."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(TelegramChannel).order_by(TelegramChannel.created_at.desc())
        )
        channels = result.scalars().all()
        
        print("\n" + "="*80)
        print("CHANNELS IN DATABASE")
        print("="*80)
        print()
        
        if not channels:
            print("No channels found in database.")
            print("Run 'python migrate_channels.py --import' to import channels.")
        else:
            print(f"Found {len(channels)} channels:\n")
            print("-"*80)
            for channel in channels:
                active = "✓" if channel.is_active else "✗"
                username = f"@{channel.username}" if channel.username else "-"
                last_scraped = channel.last_scraped_at.strftime("%Y-%m-%d %H:%M") if channel.last_scraped_at else "Never"
                print(f"[{active}] {channel.title:<35} | {channel.channel_id:>15} | {username:<20} | Last scraped: {last_scraped}")
            print("-"*80)
        print()


async def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--discover":
            print("\n🔍 Discovering Telegram channels...")
            await discover_channels()
        elif command == "--list":
            print("\n📋 Listing database channels...")
            await list_database_channels()
        elif command == "--import":
            print("\n📥 Importing channels to database...")
            await import_channels()
        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  --discover  : Discover all subscribed Telegram channels")
            print("  --list      : List channels in database")
            print("  --import    : Import channels from CHANNELS_TO_IMPORT")
    else:
        # Default: show menu
        print("\n" + "="*80)
        print("CHANNEL MIGRATION HELPER")
        print("="*80)
        print("\nAvailable commands:")
        print("  python migrate_channels.py --discover  : Find all subscribed channels")
        print("  python migrate_channels.py --list      : List channels in database")
        print("  python migrate_channels.py --import    : Import channels to database")
        print("\n" + "="*80)
        print("\nExample workflow:")
        print("  1. Run --discover to find your channel IDs")
        print("  2. Edit CHANNELS_TO_IMPORT in this script")
        print("  3. Run --import to add them to database")
        print("  4. Run 'python scraper.py' to start scraping")
        print()


if __name__ == "__main__":
    asyncio.run(main())

