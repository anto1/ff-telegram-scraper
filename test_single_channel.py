"""Quick test of single channel to verify reaction filtering"""

import asyncio
import parser

async def test_channel():
    """Test just рывок_из_бедности channel"""
    
    # Fetch channels
    await parser.fetch_all_channels()
    
    # Find the channel
    target = None
    for name in parser.CHANNELS:
        if "рывок" in name or "бедност" in name:
            target = name
            break
    
    if target:
        print(f"\nExporting {target} with DEBUG enabled...\n")
        result = await parser.export_channel(target, limit=200)
        print(f"\nDone! Check for DEBUG message for post 1856")
    else:
        print(f"Channel not found! Available channels: {list(parser.CHANNELS.keys())[:5]}")

if __name__ == "__main__":
    with parser.client:
        parser.client.loop.run_until_complete(test_channel())

