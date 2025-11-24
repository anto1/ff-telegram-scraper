"""
Quick script to analyze a specific post's reaction breakdown.

Usage: 
    python analyze_post.py
"""

import asyncio
from parser import client, get_reaction_breakdown, format_reaction_breakdown

async def analyze_specific_post():
    """Analyze the specific post requested by user."""
    
    # Post details from user request
    channel_name = "рывок_из_бедности"
    message_id = 1856
    
    print(f"\nFetching reaction breakdown for post {message_id} in channel '{channel_name}'...\n")
    
    # Get detailed breakdown
    breakdown = await get_reaction_breakdown(channel_name, message_id)
    
    if breakdown:
        # Format and display
        report = format_reaction_breakdown(breakdown)
        print(report)
        
        # Also save to file
        filename = f"reaction_breakdown_{channel_name}_{message_id}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to: {filename}\n")
    else:
        print("Failed to fetch reaction breakdown.")

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(analyze_specific_post())


