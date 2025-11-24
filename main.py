"""
FastAPI application for Telegram scraper service.

Provides REST API for managing channels and viewing statistics.
Ready for deployment on Railway with Postgres database.
"""

import os
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db, init_db
from models import TelegramChannel, TelegramMessage
from schemas import (
    ChannelCreate, ChannelUpdate, ChannelResponse, ChannelWithStats,
    MessageResponse, ChannelStats, GlobalStats,
    ScrapeRequest, ScrapeResponse
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Telegram Scraper API",
    description="REST API for managing Telegram channel scraping and analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# STARTUP & HEALTH CHECK
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("🚀 Starting Telegram Scraper API...")
    await init_db()
    logger.info("✓ Application ready!")
    logger.info("ℹ️  Telegram client will connect when scraping is triggered.")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Telegram Scraper API...")
    try:
        from scraper import client as telegram_client
        if telegram_client.is_connected():
            await telegram_client.disconnect()
            logger.info("✓ Telegram client disconnected.")
    except Exception as e:
        logger.error(f"Error disconnecting Telegram client: {e}")


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "Telegram Scraper API",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check with database connectivity test.
    Useful for Railway health checks.
    """
    try:
        # Test database connection
        result = await db.execute(select(func.count()).select_from(TelegramChannel))
        channel_count = result.scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "channels": channel_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )


# ============================================================================
# CHANNEL CRUD ENDPOINTS
# ============================================================================

@app.get("/channels", response_model=List[ChannelResponse], tags=["Channels"])
async def list_channels(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of all channels.
    
    Query parameters:
    - is_active: Filter by active status (optional)
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    """
    query = select(TelegramChannel)
    
    # Apply filters
    if is_active is not None:
        query = query.where(TelegramChannel.is_active == is_active)
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(TelegramChannel.created_at.desc())
    
    result = await db.execute(query)
    channels = result.scalars().all()
    
    return channels


@app.get("/channels/with-stats", response_model=List[ChannelWithStats], tags=["Channels"])
async def list_channels_with_stats(
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of channels with basic statistics.
    
    Includes message count and latest message date for each channel.
    """
    query = select(TelegramChannel)
    
    if is_active is not None:
        query = query.where(TelegramChannel.is_active == is_active)
    
    query = query.offset(skip).limit(limit).order_by(TelegramChannel.created_at.desc())
    
    result = await db.execute(query)
    channels = result.scalars().all()
    
    # Enrich with stats
    channels_with_stats = []
    for channel in channels:
        # Get message count
        count_query = select(func.count()).select_from(TelegramMessage).where(
            TelegramMessage.channel_id == channel.id
        )
        count_result = await db.execute(count_query)
        messages_count = count_result.scalar() or 0
        
        # Get latest message date
        latest_query = select(func.max(TelegramMessage.date)).where(
            TelegramMessage.channel_id == channel.id
        )
        latest_result = await db.execute(latest_query)
        latest_message_date = latest_result.scalar()
        
        # Get average engagement rate
        avg_query = select(func.avg(TelegramMessage.engagement_rate)).where(
            TelegramMessage.channel_id == channel.id
        ).where(TelegramMessage.views > 0)
        avg_result = await db.execute(avg_query)
        avg_engagement_rate = avg_result.scalar()
        
        # Get average views
        avg_views_query = select(func.avg(TelegramMessage.views)).where(
            TelegramMessage.channel_id == channel.id
        ).where(TelegramMessage.views > 0)
        avg_views_result = await db.execute(avg_views_query)
        avg_views = avg_views_result.scalar()
        
        # Build response
        channel_dict = {
            "id": channel.id,
            "title": channel.title,
            "username": channel.username,
            "channel_id": channel.channel_id,
            "is_active": channel.is_active,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at,
            "last_scraped_at": channel.last_scraped_at,
            "notes": channel.notes,
            "messages_count": messages_count,
            "latest_message_date": latest_message_date,
            "avg_engagement_rate": round(avg_engagement_rate, 2) if avg_engagement_rate else None,
            "avg_views": round(avg_views, 2) if avg_views else None,
        }
        
        channels_with_stats.append(ChannelWithStats(**channel_dict))
    
    return channels_with_stats


@app.get("/channels/{channel_id}", response_model=ChannelResponse, tags=["Channels"])
async def get_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific channel by ID."""
    query = select(TelegramChannel).where(TelegramChannel.id == channel_id)
    result = await db.execute(query)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with id {channel_id} not found"
        )
    
    return channel


@app.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED, tags=["Channels"])
async def create_channel(channel: ChannelCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new channel.
    
    The channel_id must be unique. If a channel with the same channel_id
    already exists, returns a 400 error.
    """
    # Check if channel_id already exists
    existing = await db.execute(
        select(TelegramChannel).where(TelegramChannel.channel_id == channel.channel_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel with channel_id {channel.channel_id} already exists"
        )
    
    # Create new channel
    db_channel = TelegramChannel(
        title=channel.title,
        username=channel.username,
        channel_id=channel.channel_id,
        is_active=channel.is_active,
        notes=channel.notes,
    )
    
    db.add(db_channel)
    await db.commit()
    await db.refresh(db_channel)
    
    return db_channel


@app.patch("/channels/{channel_id}", response_model=ChannelResponse, tags=["Channels"])
async def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing channel.
    
    Only provided fields will be updated. All fields are optional.
    """
    # Get existing channel
    query = select(TelegramChannel).where(TelegramChannel.id == channel_id)
    result = await db.execute(query)
    db_channel = result.scalar_one_or_none()
    
    if not db_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with id {channel_id} not found"
        )
    
    # Update fields if provided
    update_data = channel_update.model_dump(exclude_unset=True)
    
    # If updating channel_id, check it's not already used
    if "channel_id" in update_data and update_data["channel_id"] != db_channel.channel_id:
        existing = await db.execute(
            select(TelegramChannel).where(TelegramChannel.channel_id == update_data["channel_id"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel with channel_id {update_data['channel_id']} already exists"
            )
    
    # Apply updates
    for field, value in update_data.items():
        setattr(db_channel, field, value)
    
    db_channel.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(db_channel)
    
    return db_channel


@app.delete("/channels/{channel_id}", response_model=ChannelResponse, tags=["Channels"])
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    """
    Soft delete a channel (sets is_active = False).
    
    This is a soft delete - the channel and its messages remain in the database
    but won't be scraped anymore. To hard delete, use DELETE /channels/{id}/hard
    """
    query = select(TelegramChannel).where(TelegramChannel.id == channel_id)
    result = await db.execute(query)
    db_channel = result.scalar_one_or_none()
    
    if not db_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with id {channel_id} not found"
        )
    
    # Soft delete
    db_channel.is_active = False
    db_channel.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(db_channel)
    
    return db_channel


@app.delete("/channels/{channel_id}/hard", status_code=status.HTTP_204_NO_CONTENT, tags=["Channels"])
async def hard_delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    """
    Hard delete a channel and all its messages.
    
    WARNING: This permanently deletes the channel and all associated messages.
    This action cannot be undone.
    """
    query = select(TelegramChannel).where(TelegramChannel.id == channel_id)
    result = await db.execute(query)
    db_channel = result.scalar_one_or_none()
    
    if not db_channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with id {channel_id} not found"
        )
    
    # Hard delete (cascade will delete all messages)
    await db.delete(db_channel)
    await db.commit()
    
    return None


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@app.get("/stats/global", response_model=GlobalStats, tags=["Statistics"])
async def get_global_stats(db: AsyncSession = Depends(get_db)):
    """Get global statistics across all channels."""
    # Total channels
    total_channels_query = select(func.count()).select_from(TelegramChannel)
    total_channels_result = await db.execute(total_channels_query)
    total_channels = total_channels_result.scalar() or 0
    
    # Active channels
    active_channels_query = select(func.count()).select_from(TelegramChannel).where(
        TelegramChannel.is_active == True
    )
    active_channels_result = await db.execute(active_channels_query)
    active_channels = active_channels_result.scalar() or 0
    
    # Total messages
    total_messages_query = select(func.count()).select_from(TelegramMessage)
    total_messages_result = await db.execute(total_messages_query)
    total_messages = total_messages_result.scalar() or 0
    
    # Last scrape time
    last_scrape_query = select(func.max(TelegramChannel.last_scraped_at))
    last_scrape_result = await db.execute(last_scrape_query)
    last_scrape_time = last_scrape_result.scalar()
    
    return GlobalStats(
        total_channels=total_channels,
        active_channels=active_channels,
        total_messages=total_messages,
        last_scrape_time=last_scrape_time
    )


@app.get("/stats/channels", response_model=List[ChannelStats], tags=["Statistics"])
async def get_channel_stats(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed statistics for each channel.
    
    Includes average and median metrics for engagement, views, reactions, etc.
    """
    # Get channels
    query = select(TelegramChannel)
    if is_active is not None:
        query = query.where(TelegramChannel.is_active == is_active)
    
    result = await db.execute(query)
    channels = result.scalars().all()
    
    stats_list = []
    
    for channel in channels:
        # Get message statistics
        stats_query = select(
            func.count(TelegramMessage.id).label('total_messages'),
            func.max(TelegramMessage.date).label('latest_message_date'),
            func.avg(TelegramMessage.views).label('avg_views'),
            func.avg(TelegramMessage.total_reactions).label('avg_reactions'),
            func.avg(TelegramMessage.forwards).label('avg_forwards'),
            func.avg(TelegramMessage.replies).label('avg_replies'),
            func.avg(TelegramMessage.engagement_count).label('avg_engagement_count'),
            func.avg(TelegramMessage.engagement_rate).label('avg_engagement_rate'),
        ).where(TelegramMessage.channel_id == channel.id).where(
            TelegramMessage.views > 0  # Only count valid messages
        )
        
        stats_result = await db.execute(stats_query)
        stats_row = stats_result.one()
        
        # For median calculation, we'd need to fetch all values and calculate in Python
        # For now, we'll use averages (median requires more complex SQL or Python processing)
        
        channel_stat = ChannelStats(
            channel_id=channel.id,
            channel_title=channel.title,
            is_active=channel.is_active,
            last_scraped_at=channel.last_scraped_at,
            total_messages=stats_row.total_messages or 0,
            latest_message_date=stats_row.latest_message_date,
            avg_views=round(stats_row.avg_views, 2) if stats_row.avg_views else 0.0,
            avg_reactions=round(stats_row.avg_reactions, 2) if stats_row.avg_reactions else 0.0,
            avg_forwards=round(stats_row.avg_forwards, 2) if stats_row.avg_forwards else 0.0,
            avg_replies=round(stats_row.avg_replies, 2) if stats_row.avg_replies else 0.0,
            avg_engagement_count=round(stats_row.avg_engagement_count, 2) if stats_row.avg_engagement_count else 0.0,
            avg_engagement_rate=round(stats_row.avg_engagement_rate, 4) if stats_row.avg_engagement_rate else 0.0,
            # Note: median calculation would require fetching all values or using percentile_cont in Postgres
            median_views=round(stats_row.avg_views, 2) if stats_row.avg_views else 0.0,  # Placeholder
            median_reactions=round(stats_row.avg_reactions, 2) if stats_row.avg_reactions else 0.0,  # Placeholder
            median_engagement_rate=round(stats_row.avg_engagement_rate, 4) if stats_row.avg_engagement_rate else 0.0,  # Placeholder
        )
        
        stats_list.append(channel_stat)
    
    return stats_list


@app.get("/channels/{channel_id}/messages", response_model=List[MessageResponse], tags=["Messages"])
async def get_channel_messages(
    channel_id: int,
    skip: int = 0,
    limit: int = 50,
    order_by: str = "date",  # date, engagement_rate, engagement_count, views
    order: str = "desc",  # asc or desc
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a specific channel.
    
    Supports pagination and sorting by various metrics.
    """
    # Verify channel exists
    channel_query = select(TelegramChannel).where(TelegramChannel.id == channel_id)
    channel_result = await db.execute(channel_query)
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with id {channel_id} not found"
        )
    
    # Build query
    query = select(TelegramMessage).where(TelegramMessage.channel_id == channel_id)
    
    # Apply ordering
    order_column = {
        "date": TelegramMessage.date,
        "engagement_rate": TelegramMessage.engagement_rate,
        "engagement_count": TelegramMessage.engagement_count,
        "views": TelegramMessage.views,
    }.get(order_by, TelegramMessage.date)
    
    if order == "desc":
        query = query.order_by(desc(order_column))
    else:
        query = query.order_by(order_column)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return messages


# ============================================================================
# SCRAPER ENDPOINTS
# ============================================================================

@app.post("/scrape", response_model=ScrapeResponse, tags=["Scraper"])
async def trigger_scrape(
    scrape_request: ScrapeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger scraping of Telegram channels.
    
    This endpoint initiates the scraping process and returns results immediately.
    For production deployments with many channels, consider implementing this as 
    a background task using Celery or similar to avoid request timeouts.
    """
    started_at = datetime.utcnow()
    
    # Import scraper functions (circular import prevention)
    try:
        from scraper import scrape_all_active_channels, scrape_specific_channels
    except ImportError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Scraper module import failed: {str(e)}"
        )
    
    # Trigger scraping based on request
    try:
        if scrape_request.channel_ids:
            # Scrape specific channels by their internal DB IDs
            result = await scrape_specific_channels(db, scrape_request.channel_ids, limit=200)
        else:
            # Scrape all active channels
            result = await scrape_all_active_channels(db, limit=200)
        
        completed_at = datetime.utcnow()
        
        return ScrapeResponse(
            success=result.get("success", True),
            channels_processed=result.get("channels_processed", 0),
            total_messages_scraped=result.get("total_messages_scraped", 0),
            errors=result.get("errors", []),
            started_at=started_at,
            completed_at=completed_at
        )
    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=True)
        completed_at = datetime.utcnow()
        return ScrapeResponse(
            success=False,
            channels_processed=0,
            total_messages_scraped=0,
            errors=[str(e)],
            started_at=started_at,
            completed_at=completed_at
        )


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Railway sets PORT env var)
    port = int(os.getenv("PORT", 8000))
    
    # Run server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Disable in production
        log_level="info"
    )

