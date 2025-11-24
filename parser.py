"""
Telegram Channel Parser & Analytics Tool

This script analyzes Telegram channels to track engagement metrics including:
- Views, reactions, forwards, and replies
- Engagement rates and counts
- Channel subscriber statistics
- Top performing posts across all channels

Features:
- Automatically discovers all subscribed channels
- Excludes paid Telegram Stars reactions
- Calculates median engagement metrics per channel
- Generates rankings and statistics reports
"""

import os
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient
import statistics

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials (get from https://my.telegram.org)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Initialize Telegram client with session file
client = TelegramClient("test_session", API_ID, API_HASH)

# Dictionary to store channel names and IDs (populated dynamically)
# Old hardcoded channels (kept for reference):
# CHANNELS = {
#     "pokerok": -1001213573012,
#     "posidelki_s_shakhovtsom": -1001418874148,
#     "a_game": -1001868304845,
#     "chto_na_rivere": -1001207505171,
#     "spr_poker": -1001469944207,
#     "misha_inner": -1001455436304,
# }

CHANNELS = {}  # Will be populated by fetch_all_channels()


# ============================================================================
# METRICS CALCULATION FUNCTIONS
# ============================================================================


def get_total_reactions(message):
    """
    Calculate total reaction count for a message, excluding paid reactions.
    
    Telegram has two types of reactions:
    - Free reactions: Standard emoji reactions (👍, ❤️, etc.)
    - Paid reactions: Custom emoji reactions (Telegram Stars)
    
    We only count free reactions to measure genuine organic engagement.
    
    Args:
        message: Telegram message object
        
    Returns:
        int: Total count of free reactions
    """
    # Check if message has any reactions
    if not message.reactions:
        return 0
    
    # Get the reaction results list
    results = getattr(message.reactions, "results", None)
    if not results:
        return 0
    
    total_free = 0
    total_paid = 0
    debug_types = {}  # Track all reaction types for debugging
    
    # Iterate through each reaction type on the message
    for r in results:
        # Get the reaction object (contains type info)
        reaction = getattr(r, "reaction", None)
        count = getattr(r, "count", 0) or 0
        
        if not reaction:
            # If no reaction object, count it as free (backward compatibility)
            total_free += count
            debug_types["None"] = debug_types.get("None", 0) + count
            continue
        
        # Check if it's a paid reaction (Telegram Stars / custom emoji)
        # ReactionPaid = paid reactions with stars (we skip these)
        # ReactionCustomEmoji = paid custom emoji reactions (we skip these)
        # ReactionEmoji = free standard emoji reactions (we count these)
        reaction_type = type(reaction).__name__
        debug_types[reaction_type] = debug_types.get(reaction_type, 0) + count
        
        if reaction_type in ("ReactionPaid", "ReactionCustomEmoji"):
            total_paid += count  # Track but don't include in total
            continue  # Skip paid reactions
        else:
            # Free reaction (ReactionEmoji or other types)
            total_free += count
    
    # Debug for message 1856 in рывок_из_бедности
    # Uncomment to see breakdown:
    # if message.id == 1856:
    #     print(f"DEBUG Message {message.id}: Free={total_free}, Paid={total_paid}, Total={total_free+total_paid}")
    #     print(f"  Reaction types breakdown: {debug_types}")
    
    return total_free


def calculate_engagement(message, total_reactions):
    """
    Calculate comprehensive engagement metrics for a message.
    
    Engagement includes all user interactions:
    - Reactions: Emoji responses to the post
    - Forwards: Times the post was shared/forwarded
    - Replies: Number of comments/replies on the post
    
    Args:
        message: Telegram message object
        total_reactions: Pre-calculated total reaction count (free reactions only)
        
    Returns:
        dict: {
            "engagement_count": Total number of interactions,
            "engagement_rate": Percentage of viewers who engaged (0-100)
        }
    """
    # Extract metrics from message, defaulting to 0 if not available
    views = message.views or 0
    forwards = message.forwards or 0
    replies = getattr(message.replies, "replies", None) if message.replies else 0
    replies = replies or 0
    
    # Total engagement count = sum of all interactions
    engagement_count = total_reactions + forwards + replies
    
    # Engagement rate = what % of viewers interacted with the post
    # Higher is better (means content resonated with audience)
    engagement_rate = (engagement_count / views * 100) if views > 0 else 0
    
    return {
        "engagement_count": engagement_count,
        "engagement_rate": round(engagement_rate, 4)  # Round to 4 decimal places
    }


def calculate_channel_stats(channel_data_list):
    """
    Calculate statistics for each channel.
    
    Uses median instead of average because it's more robust to outliers
    (e.g., one viral post won't skew the typical performance metrics).
    
    Args:
        channel_data_list: List of dicts with 'messages', 'subscribers', 'channel_name'
    
    Returns:
        List of channel stats sorted by subscribers (descending)
    """
    stats = []
    
    for channel_data in channel_data_list:
        messages = channel_data["messages"]
        channel_name = channel_data["channel_name"]
        subscribers = channel_data["subscribers"]
        
        # Filter out messages without views (drafts, deleted, etc.)
        valid_messages = [m for m in messages if (m.get("views") or 0) > 0]
        
        if not valid_messages:
            continue
        
        # Extract all metrics into lists for median calculation
        views_list = [m["views"] for m in valid_messages if m.get("views")]
        reactions_list = [m["total_reactions"] for m in valid_messages if m.get("total_reactions") is not None]
        comments_list = [m["replies"] or 0 for m in valid_messages if m.get("replies") is not None]
        forwards_list = [m["forwards"] or 0 for m in valid_messages if m.get("forwards") is not None]
        post_length_list = [m["post_length"] for m in valid_messages if m.get("post_length") is not None]
        engagement_rates = [m["engagement_rate"] for m in valid_messages if m.get("engagement_rate") is not None]
        engagement_counts = [m["engagement_count"] for m in valid_messages if m.get("engagement_count") is not None]
        
        # Build statistics dictionary for this channel
        stats.append({
            "channel": channel_name,
            "subscribers": subscribers,
            "posts_analyzed": len(valid_messages),
            "median_post_length": statistics.median(post_length_list) if post_length_list else 0,
            "median_views": statistics.median(views_list) if views_list else 0,
            "median_reactions": statistics.median(reactions_list) if reactions_list else 0,
            "median_forwards": statistics.median(forwards_list) if forwards_list else 0,
            "median_comments": statistics.median(comments_list) if comments_list else 0,
            "median_engagement_count": statistics.median(engagement_counts) if engagement_counts else 0,
            "median_engagement_rate": statistics.median(engagement_rates) if engagement_rates else 0,
        })
    
    # Sort by subscribers (highest first)
    stats.sort(key=lambda x: x["subscribers"], reverse=True)
    
    return stats


def format_channel_stats_table(stats):
    """
    Format channel statistics as a human-readable ASCII table.
    
    Creates a formatted table with proper alignment and thousands separators
    for easy reading in console or text file.
    
    Args:
        stats: List of channel statistics dictionaries
        
    Returns:
        str: Formatted table as a multi-line string
    """
    if not stats:
        return "No channel statistics available."
    
    # Table header with column titles
    lines = []
    lines.append("\n" + "="*180)
    lines.append("CHANNEL STATISTICS (Sorted by Subscribers)")
    lines.append("="*180)
    lines.append(
        f"{'Channel':<30} | {'Subs':>10} | {'Posts':>6} | {'Med Len':>8} | "
        f"{'Med Views':>10} | {'Med React':>10} | {'Med Fwds':>9} | {'Med Cmnts':>10} | "
        f"{'Med Eng':>10} | {'Med Eng %':>10}"
    )
    lines.append("-"*180)
    
    # Table rows - one per channel
    for stat in stats:
        lines.append(
            f"{stat['channel']:<30} | "
            f"{stat['subscribers']:>10,} | "
            f"{stat['posts_analyzed']:>6} | "
            f"{stat['median_post_length']:>8,.0f} | "
            f"{stat['median_views']:>10,.0f} | "
            f"{stat['median_reactions']:>10,.1f} | "
            f"{stat['median_forwards']:>9,.1f} | "
            f"{stat['median_comments']:>10,.1f} | "
            f"{stat['median_engagement_count']:>10,.1f} | "
            f"{stat['median_engagement_rate']:>9.2f}%"
        )
    
    # Table footer with legend
    lines.append("="*180)
    lines.append("\nLegend:")
    lines.append("  Subs = Subscribers (total channel members)")
    lines.append("  Posts = Number of posts analyzed")
    lines.append("  Med Len = Median post length (characters)")
    lines.append("  Med Views = Median views per post")
    lines.append("  Med React = Median reactions per post (free reactions only, excludes Telegram Stars)")
    lines.append("  Med Fwds = Median forwards per post")
    lines.append("  Med Cmnts = Median comments/replies per post")
    lines.append("  Med Eng = Median engagement count per post (reactions + forwards + comments)")
    lines.append("  Med Eng % = Median engagement rate (% of viewers who engaged)")
    lines.append("="*180 + "\n")
    
    return "\n".join(lines)


def save_channel_stats_csv(stats, filename):
    """
    Save channel statistics to a CSV file for easy import into Excel/Sheets.
    
    CSV format is ideal for:
    - Opening in Excel, Google Sheets, or other spreadsheet tools
    - Further data analysis and visualization
    - Importing into databases or BI tools
    
    Args:
        stats: List of channel statistics dictionaries
        filename: Output CSV filename
        
    Returns:
        None
        
    Side effects:
        - Creates a CSV file with the statistics
    """
    if not stats:
        print("No statistics to save to CSV.")
        return
    
    # Define CSV columns in the order we want them
    fieldnames = [
        'channel',
        'subscribers',
        'posts_analyzed',
        'median_post_length',
        'median_views',
        'median_reactions',
        'median_forwards',
        'median_comments',
        'median_engagement_count',
        'median_engagement_rate'
    ]
    
    # Write CSV file with UTF-8 encoding
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header row
        writer.writeheader()
        
        # Write data rows
        for stat in stats:
            writer.writerow(stat)


# ============================================================================
# RANKING & ANALYSIS FUNCTIONS
# ============================================================================


def collect_top_posts(messages_all, top_n=5, sort_by="engagement_rate"):
    """
    Find the top N best-performing posts across all channels.
    
    Analyzes all posts and ranks them by a specified metric to identify
    the most successful content. Useful for understanding what type of
    content resonates best with the audience.
    
    Args:
        messages_all: List of all message dictionaries from all channels
        top_n: Number of top posts to return (default: 5)
        sort_by: Metric to sort by. Options:
                 - "engagement_rate": % of viewers who engaged (best for quality)
                 - "engagement_count": Total interactions (best for viral content)
                 - "total_reactions": Most reactions
                 - "views": Most viewed
                 - "reactions_per_view": Reaction efficiency
                 
    Returns:
        List of top N posts with all their metrics
    """
    scored = []

    # Process each message and calculate all metrics
    for msg in messages_all:
        views = msg["views"] or 0
        reactions = msg["total_reactions"] or 0
        engagement_count = msg.get("engagement_count", 0) or 0
        engagement_rate = msg.get("engagement_rate", 0) or 0

        # Skip posts with no views or no engagement (invalid data)
        if views <= 0 or engagement_count <= 0:
            continue

        # Calculate reaction efficiency (reactions as % of views)
        reactions_per_view = reactions / views if views > 0 else 0

        # Build complete post data for ranking
        scored.append({
            "channel": msg["channel"],
            "id": msg["id"],
            "date": msg["date"],
            "text_preview": (msg["text"][:120] + "…") if msg["text"] and len(msg["text"]) > 120 else msg["text"],
            "views": views,
            "forwards": msg.get("forwards", 0) or 0,
            "replies": msg.get("replies", 0) or 0,
            "total_reactions": reactions,
            "engagement_count": engagement_count,
            "engagement_rate": engagement_rate,
            "reactions_per_view": round(reactions_per_view, 6)
        })

    # Sort by specified metric (highest first)
    scored.sort(key=lambda x: x.get(sort_by, 0), reverse=True)

    # Return only top N posts
    return scored[:top_n]


# ============================================================================
# CHANNEL DISCOVERY & DATA COLLECTION FUNCTIONS
# ============================================================================


async def fetch_all_channels():
    """
    Automatically discover all Telegram channels the user is subscribed to.
    
    Scans through all user's dialogs and identifies channels (as opposed to
    groups or direct messages). Creates clean, filesystem-safe names for each
    channel to use in filenames.
    
    Returns:
        dict: Dictionary mapping clean channel names to channel IDs
        
    Side effects:
        - Updates global CHANNELS dictionary
        - Prints progress to console
    """
    global CHANNELS
    channels_dict = {}
    
    print("Fetching all your subscribed channels...")
    
    # Iterate through all dialogs (chats) the user has
    async for dialog in client.iter_dialogs():
        # Filter: only channels (not groups, not private chats)
        # is_channel: True for both channels and megagroups
        # is_group: True only for megagroups
        # So: is_channel=True and is_group=False means it's a channel
        if dialog.is_channel and not dialog.is_group:
            # Get original channel name
            name = dialog.name
            
            # Create a filesystem-safe name for use in filenames
            # Example: "Poker News 🃏" -> "poker_news"
            clean_name = name.lower().replace(" ", "_").replace("-", "_")
            clean_name = "".join(c for c in clean_name if c.isalnum() or c == "_")
            
            # Store channel with its ID
            channels_dict[clean_name] = dialog.id
            print(f"  Found: {name} (ID: {dialog.id})")
    
    # Update global CHANNELS dictionary
    CHANNELS = channels_dict
    print(f"\nTotal channels found: {len(CHANNELS)}\n")
    
    return channels_dict


async def export_channel(name: str, limit: int = 200):
    """
    Fetch and analyze all posts from a single Telegram channel.
    
    Downloads recent posts from the channel, calculates engagement metrics for
    each post, fetches subscriber count, and exports everything to a JSON file.
    
    Args:
        name: Clean channel name (as stored in CHANNELS dict)
        limit: Maximum number of recent posts to fetch (default: 200)
        
    Returns:
        dict: {
            "messages": List of message dictionaries with metrics,
            "subscribers": Total subscriber count,
            "channel_name": Channel name
        }
        
    Side effects:
        - Saves JSON file: export_{channel_name}_{timestamp}.json
        - Prints progress to console
    """
    channel_id = CHANNELS[name]
    messages_data = []

    # Fetch channel entity (contains metadata like subscriber count)
    channel_entity = await client.get_entity(channel_id)
    
    # Try to get subscriber count
    # Method 1: Get participants (more accurate but may be restricted)
    try:
        full_channel = await client.get_participants(channel_entity, limit=0)
        subscribers = full_channel.total
    except Exception as e:
        # Method 2: Fallback to participants_count attribute
        # (less accurate but available on all channels)
        subscribers = getattr(channel_entity, 'participants_count', None)
        if subscribers is None:
            print(f"  ⚠️  Could not fetch subscriber count for {name}")
            subscribers = 0

    # Fetch recent messages from the channel
    async for message in client.iter_messages(channel_id, limit=limit):
        # Calculate engagement metrics for this message
        total_reactions = get_total_reactions(message)  # Free reactions only
        engagement = calculate_engagement(message, total_reactions)

        # Calculate post length (character count)
        post_length = len(message.text) if message.text else 0
        
        # Build comprehensive message data dictionary
        messages_data.append({
            "channel": name,
            "id": message.id,
            "date": message.date.isoformat() if message.date else None,
            "sender_id": message.sender_id,
            "text": message.text,
            "post_length": post_length,
            "views": message.views,
            "forwards": message.forwards,
            "replies": getattr(message.replies, "replies", None) if message.replies else None,
            "total_reactions": total_reactions,
            "engagement_count": engagement["engagement_count"],
            "engagement_rate": engagement["engagement_rate"],
        })

    # Reverse to chronological order (API returns newest first)
    messages_data.reverse()

    # Save channel data to JSON file
    filename = f"export_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(messages_data, f, ensure_ascii=False, indent=2)

    print(f"[{name}] saved {len(messages_data)} messages to {filename} | Subscribers: {subscribers:,}")
    
    # Return structured data for further analysis
    return {
        "messages": messages_data,
        "subscribers": subscribers,
        "channel_name": name
    }


# ============================================================================
# MAIN EXECUTION FUNCTION
# ============================================================================


async def main(test_mode=True, test_channels_limit=3):
    """
    Main orchestration function - runs the complete analysis pipeline.
    
    Pipeline steps:
    1. Authenticate with Telegram
    2. Discover all subscribed channels
    3. Select channels to process (test mode or full mode)
    4. Fetch and analyze posts from each channel
    5. Generate top post rankings across all channels
    6. Calculate and display channel statistics
    7. Export all results to files
    
    Args:
        test_mode: If True, only process first N channels (for testing)
        test_channels_limit: Number of channels to process in test mode
        
    Side effects:
        - Creates multiple JSON and TXT files with results
        - Prints progress and statistics to console
    """
    # ========================================================================
    # STEP 1: Authentication
    # ========================================================================
    me = await client.get_me()
    print("Logged in as:", me.username or me.first_name)
    print()

    # ========================================================================
    # STEP 2: Channel Discovery
    # ========================================================================
    await fetch_all_channels()

    # ========================================================================
    # STEP 3: Select Channels to Process
    # ========================================================================
    if test_mode:
        # Test mode: Only process first N channels (faster, for testing)
        channels_to_process = dict(list(CHANNELS.items())[:test_channels_limit])
        print(f"\n🧪 TEST MODE: Processing only {len(channels_to_process)} channels")
        print(f"Channels: {', '.join(channels_to_process.keys())}\n")
    else:
        # Full mode: Process all discovered channels
        channels_to_process = CHANNELS
        print(f"\n📊 FULL MODE: Processing all {len(channels_to_process)} channels\n")

    # ========================================================================
    # STEP 4: Fetch and Analyze Channel Data
    # ========================================================================
    limit = 200  # Number of recent posts to fetch per channel
    all_messages = []  # Combined list of all messages from all channels
    channel_data_list = []  # List of channel data with subscribers

    # Process each channel one by one
    for name in channels_to_process:
        print(f"\nProcessing {name}...")
        channel_data = await export_channel(name, limit=limit)
        channel_data_list.append(channel_data)
        all_messages.extend(channel_data["messages"])

    # ========================================================================
    # STEP 5: Generate Top Post Rankings
    # ========================================================================
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("\n" + "="*60)
    print("GENERATING TOP 5 RANKINGS")
    print("="*60)
    
    # Ranking 1: Top posts by engagement rate (% of viewers who engaged)
    # This identifies quality content that resonates with the audience
    top5_engagement_rate = collect_top_posts(all_messages, top_n=5, sort_by="engagement_rate")
    out_name_eng_rate = f"top5_by_engagement_rate_{timestamp}.json"
    with open(out_name_eng_rate, "w", encoding="utf-8") as f:
        json.dump(top5_engagement_rate, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Top 5 by Engagement Rate saved to: {out_name_eng_rate}")
    
    # Ranking 2: Top posts by total engagement count
    # This identifies viral content with most total interactions
    top5_engagement_count = collect_top_posts(all_messages, top_n=5, sort_by="engagement_count")
    out_name_eng_count = f"top5_by_engagement_count_{timestamp}.json"
    with open(out_name_eng_count, "w", encoding="utf-8") as f:
        json.dump(top5_engagement_count, f, ensure_ascii=False, indent=2)
    print(f"✓ Top 5 by Engagement Count saved to: {out_name_eng_count}")
    
    # Ranking 3: Top posts by reactions (classic metric for comparison)
    # This identifies posts that got the most reactions specifically
    top5_reactions = collect_top_posts(all_messages, top_n=5, sort_by="total_reactions")
    out_name_reactions = f"top5_by_reactions_{timestamp}.json"
    with open(out_name_reactions, "w", encoding="utf-8") as f:
        json.dump(top5_reactions, f, ensure_ascii=False, indent=2)
    print(f"✓ Top 5 by Reactions saved to: {out_name_reactions}")
    
    print("\n" + "="*60)
    print("Done! All rankings saved.")
    print("="*60)
    
    # ========================================================================
    # STEP 6: Generate Channel Statistics
    # ========================================================================
    # Calculate median metrics for each channel
    channel_stats = calculate_channel_stats(channel_data_list)
    stats_table = format_channel_stats_table(channel_stats)
    
    # Display table in console
    print(stats_table)
    
    # Save statistics to multiple file formats
    # JSON: Machine-readable, good for programmatic access
    stats_json_file = f"channel_statistics_{timestamp}.json"
    with open(stats_json_file, "w", encoding="utf-8") as f:
        json.dump(channel_stats, f, ensure_ascii=False, indent=2)
    
    # TXT: Human-readable formatted table
    stats_txt_file = f"channel_statistics_{timestamp}.txt"
    with open(stats_txt_file, "w", encoding="utf-8") as f:
        f.write(stats_table)
    
    # CSV: Spreadsheet-friendly format (Excel, Google Sheets)
    stats_csv_file = f"channel_statistics_{timestamp}.csv"
    save_channel_stats_csv(channel_stats, stats_csv_file)
    
    print(f"📊 Channel statistics saved to:")
    print(f"   - {stats_json_file} (JSON - machine-readable)")
    print(f"   - {stats_txt_file} (TXT - formatted table)")
    print(f"   - {stats_csv_file} (CSV - for Excel/Sheets)\n")



# ============================================================================
# UTILITY FUNCTIONS FOR INDIVIDUAL POST ANALYSIS
# ============================================================================


async def get_reaction_breakdown(channel_name: str, message_id: int):
    """
    Get detailed reaction breakdown for a specific post.
    
    Shows each emoji/reaction type and how many people used it.
    Useful for understanding which types of reactions a post received.
    
    Args:
        channel_name: Clean channel name (as stored in CHANNELS dict)
        message_id: The message ID to analyze
        
    Returns:
        dict: Detailed breakdown of reactions
    """
    # Ensure channels are loaded
    if not CHANNELS:
        await fetch_all_channels()
    
    if channel_name not in CHANNELS:
        print(f"Channel '{channel_name}' not found in subscribed channels.")
        return None
    
    channel_id = CHANNELS[channel_name]
    
    # Get the specific message
    try:
        message = await client.get_messages(channel_id, ids=message_id)
        
        if not message:
            print(f"Message {message_id} not found in channel {channel_name}")
            return None
        
        # Build detailed breakdown
        breakdown = {
            "channel": channel_name,
            "message_id": message_id,
            "date": message.date.isoformat() if message.date else None,
            "text_preview": (message.text[:200] + "…") if message.text and len(message.text) > 200 else message.text,
            "views": message.views,
            "forwards": message.forwards,
            "replies": getattr(message.replies, "replies", None) if message.replies else 0,
            "reactions_breakdown": []
        }
        
        # Get reaction details
        if message.reactions:
            results = getattr(message.reactions, "results", None)
            if results:
                total_free_reactions = 0
                total_paid_reactions = 0
                
                for r in results:
                    reaction = getattr(r, "reaction", None)
                    if not reaction:
                        continue
                    
                    count = getattr(r, "count", 0) or 0
                    reaction_type = type(reaction).__name__
                    
                    # Get emoji or reaction identifier
                    if reaction_type == "ReactionEmoji":
                        # Free emoji reaction
                        emoji = getattr(reaction, "emoticon", "Unknown")
                        breakdown["reactions_breakdown"].append({
                            "emoji": emoji,
                            "count": count,
                            "type": "free",
                            "reaction_type": reaction_type
                        })
                        total_free_reactions += count
                        
                    elif reaction_type == "ReactionCustomEmoji":
                        # Paid custom emoji (Telegram Stars)
                        custom_emoji_id = getattr(reaction, "document_id", "Unknown")
                        breakdown["reactions_breakdown"].append({
                            "emoji": f"[Custom Emoji: {custom_emoji_id}]",
                            "count": count,
                            "type": "paid",
                            "reaction_type": reaction_type
                        })
                        total_paid_reactions += count
                    else:
                        # Other reaction type
                        breakdown["reactions_breakdown"].append({
                            "emoji": f"[{reaction_type}]",
                            "count": count,
                            "type": "other",
                            "reaction_type": reaction_type
                        })
                
                # Sort by count (highest first)
                breakdown["reactions_breakdown"].sort(key=lambda x: x["count"], reverse=True)
                
                # Add totals
                breakdown["total_free_reactions"] = total_free_reactions
                breakdown["total_paid_reactions"] = total_paid_reactions
                breakdown["total_all_reactions"] = total_free_reactions + total_paid_reactions
        
        return breakdown
        
    except Exception as e:
        print(f"Error fetching message: {e}")
        return None


def format_reaction_breakdown(breakdown):
    """
    Format reaction breakdown as a readable report.
    
    Args:
        breakdown: Dictionary from get_reaction_breakdown()
        
    Returns:
        str: Formatted report
    """
    if not breakdown:
        return "No breakdown available."
    
    lines = []
    lines.append("\n" + "="*80)
    lines.append("REACTION BREAKDOWN FOR POST")
    lines.append("="*80)
    lines.append(f"Channel: {breakdown['channel']}")
    lines.append(f"Message ID: {breakdown['message_id']}")
    lines.append(f"Date: {breakdown['date']}")
    lines.append(f"Views: {breakdown['views']:,}")
    lines.append(f"Forwards: {breakdown['forwards']}")
    lines.append(f"Replies: {breakdown['replies']}")
    lines.append("")
    lines.append(f"Text Preview:")
    lines.append(f"  {breakdown['text_preview']}")
    lines.append("")
    lines.append("-"*80)
    lines.append("REACTIONS:")
    lines.append("-"*80)
    
    if breakdown.get("reactions_breakdown"):
        # Group by type
        free_reactions = [r for r in breakdown["reactions_breakdown"] if r["type"] == "free"]
        paid_reactions = [r for r in breakdown["reactions_breakdown"] if r["type"] == "paid"]
        
        if free_reactions:
            lines.append("\n🆓 FREE REACTIONS (Standard Emoji):")
            for r in free_reactions:
                emoji_display = r["emoji"]
                lines.append(f"  {emoji_display:<10} → {r['count']:>6,} reactions")
        
        if paid_reactions:
            lines.append("\n💰 PAID REACTIONS (Telegram Stars / Custom Emoji):")
            for r in paid_reactions:
                emoji_display = r["emoji"]
                lines.append(f"  {emoji_display:<30} → {r['count']:>6,} reactions")
        
        lines.append("")
        lines.append("-"*80)
        lines.append("TOTALS:")
        lines.append(f"  Free Reactions:  {breakdown.get('total_free_reactions', 0):>6,}")
        lines.append(f"  Paid Reactions:  {breakdown.get('total_paid_reactions', 0):>6,}")
        lines.append(f"  Total Reactions: {breakdown.get('total_all_reactions', 0):>6,}")
        
        # Calculate engagement
        total_engagement = (breakdown.get('total_all_reactions', 0) + 
                          breakdown.get('forwards', 0) + 
                          breakdown.get('replies', 0))
        engagement_rate = (total_engagement / breakdown['views'] * 100) if breakdown['views'] > 0 else 0
        
        lines.append("")
        lines.append(f"  Total Engagement: {total_engagement:>6,} (reactions + forwards + replies)")
        lines.append(f"  Engagement Rate:  {engagement_rate:>6.2f}%")
    else:
        lines.append("\nNo reactions found on this post.")
    
    lines.append("="*80 + "\n")
    
    return "\n".join(lines)


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    """
    Script entry point - run this file to execute the analysis.
    
    Usage:
        python parser.py
    
    Configuration:
        Change the parameters in main() call below:
        
        Test mode (faster, good for testing):
            main(test_mode=True, test_channels_limit=3)
            - Processes only first 3 channels
            - Quick way to verify everything works
        
        Full mode (complete analysis):
            main(test_mode=False)
            - Processes ALL subscribed channels
            - Use this for final results
    
    Requirements:
        - .env file with API_ID and API_HASH
        - Active internet connection
        - Telegram account with channel subscriptions
    """
    
    # Initialize Telegram client and run main analysis
    with client:
        # FULL MODE: Processing all channels with CORRECTED reaction filtering
        # Now correctly excludes BOTH ReactionPaid and ReactionCustomEmoji
        client.loop.run_until_complete(main(test_mode=False))
