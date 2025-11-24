"""
FastAPI application for Telegram scraper service.

Provides REST API for managing channels and viewing statistics.
Ready for deployment on Railway with Postgres database.
"""

import os
import logging
from datetime import datetime, timezone
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
    ScrapeRequest, ScrapeResponse,
    AuthStartRequest, AuthStartResponse, AuthVerifyRequest, AuthVerifyResponse,
    ColorFlagUpdate
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

# Configure CORS origins from environment variable or use defaults
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "https://poker-news.partdirector.ch,http://localhost:3000,http://localhost:5173"
).split(",")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for origins: {cors_origins}")


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
        "timestamp": datetime.now(timezone.utc).isoformat()
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
            "timestamp": datetime.now(timezone.utc).isoformat()
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
            "subscriber_count": channel.subscriber_count,
            "color_flag": channel.color_flag,
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
    
    db_channel.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(db_channel)
    
    return db_channel


@app.patch("/channels/{channel_id}/color-flag", response_model=ChannelResponse, tags=["Channels"])
async def update_channel_color_flag(
    channel_id: int,
    color_flag_update: ColorFlagUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update the color flag for a specific channel.
    
    This is a dedicated endpoint for updating just the color_flag field,
    which is used by the frontend for channel categorization/visualization.
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
    
    # Update color flag
    db_channel.color_flag = color_flag_update.color_flag
    db_channel.updated_at = datetime.now(timezone.utc)
    
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
    db_channel.updated_at = datetime.now(timezone.utc)
    
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


@app.post("/auth/start", response_model=AuthStartResponse, tags=["Authentication"])
async def auth_start(request: AuthStartRequest):
    """
    Step 1: Start Telegram authentication.
    
    Sends a verification code to the provided phone number via Telegram.
    Returns a phone_code_hash that must be used in the verify step.
    """
    try:
        from scraper import client as telegram_client
        
        # Ensure client is connected
        if not telegram_client.is_connected():
            await telegram_client.connect()
        
        logger.info(f"📱 Starting auth for phone: {request.phone_number}")
        
        # Send code request
        sent_code = await telegram_client.send_code_request(request.phone_number)
        
        return AuthStartResponse(
            success=True,
            message=f"Verification code sent to {request.phone_number}",
            phone_code_hash=sent_code.phone_code_hash
        )
        
    except Exception as e:
        logger.error(f"Auth start failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send verification code: {str(e)}"
        )


@app.post("/auth/verify", response_model=AuthVerifyResponse, tags=["Authentication"])
async def auth_verify(request: AuthVerifyRequest):
    """
    Step 2: Complete Telegram authentication.
    
    Verifies the code received via Telegram and completes the authentication.
    This will create/update the telegram_session.session file on the server.
    """
    try:
        from scraper import client as telegram_client
        
        # Ensure client is connected
        if not telegram_client.is_connected():
            await telegram_client.connect()
        
        logger.info(f"🔐 Verifying code for phone: {request.phone_number}")
        
        # Sign in with the code
        me = await telegram_client.sign_in(
            phone=request.phone_number,
            code=request.code,
            phone_code_hash=request.phone_code_hash
        )
        
        user_info = {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone
        }
        
        logger.info(f"✅ Authentication successful for {me.first_name}")
        
        return AuthVerifyResponse(
            success=True,
            message=f"Successfully authenticated as {me.first_name}",
            user_info=user_info
        )
        
    except Exception as e:
        logger.error(f"Auth verification failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to verify code: {str(e)}"
        )


@app.get("/auth/status", tags=["Authentication"])
async def auth_status():
    """
    Check if Telegram client is authenticated.
    
    Returns information about the current authentication status.
    """
    try:
        from scraper import client as telegram_client
        
        # Ensure client is connected
        if not telegram_client.is_connected():
            await telegram_client.connect()
        
        try:
            me = await telegram_client.get_me()
            if me:
                return {
                    "authenticated": True,
                    "user": {
                        "id": me.id,
                        "first_name": me.first_name,
                        "last_name": me.last_name,
                        "username": me.username,
                        "phone": me.phone
                    }
                }
            else:
                return {
                    "authenticated": False,
                    "message": "No active session"
                }
        except Exception:
            return {
                "authenticated": False,
                "message": "Session invalid or expired"
            }
            
    except Exception as e:
        logger.error(f"Auth status check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check auth status: {str(e)}"
        )


@app.post("/channels/import-subscriptions", tags=["Channels"])
async def import_subscriptions(db: AsyncSession = Depends(get_db)):
    """
    Import all subscribed Telegram channels into the database.
    
    Fetches all channels the authenticated user is subscribed to and adds them to the database.
    Skips channels that already exist.
    """
    try:
        from scraper import client as telegram_client
        
        # Ensure client is connected
        if not telegram_client.is_connected():
            await telegram_client.connect()
        
        logger.info("📡 Fetching subscribed channels from Telegram...")
        
        # Import required for full channel info
        from telethon.tl.functions.channels import GetFullChannelRequest
        
        # Step 1: Collect all channels from Telegram first
        telegram_channels = []
        async for dialog in telegram_client.iter_dialogs():
            # Only process channels (not groups or users)
            if dialog.is_channel and not dialog.is_group:
                channel = dialog.entity
                channel_id = channel.id
                
                # Make it negative if it's a megagroup/channel
                if not str(channel_id).startswith('-100'):
                    channel_id = int(f"-100{channel_id}")
                
                username = channel.username or "no_username"
                title = channel.title
                
                # Get subscriber count by fetching full channel info
                subscriber_count = None
                try:
                    full_channel = await telegram_client(GetFullChannelRequest(channel=channel))
                    subscriber_count = full_channel.full_chat.participants_count
                except Exception as e:
                    logger.warning(f"Could not get subscriber count for {title}: {e}")
                
                telegram_channels.append({
                    "title": title,
                    "username": username,
                    "channel_id": channel_id,
                    "subscriber_count": subscriber_count
                })
        
        logger.info(f"Found {len(telegram_channels)} channels on Telegram")
        
        # Step 2: Process channels with database (separate from Telegram iteration)
        channels_added = []
        channels_skipped = []
        channels_failed = []
        
        for channel_data in telegram_channels:
            title = channel_data["title"]
            username = channel_data["username"]
            channel_id = channel_data["channel_id"]
            subscriber_count = channel_data.get("subscriber_count")
            
            try:
                # Check if channel already exists
                result = await db.execute(
                    select(TelegramChannel).where(TelegramChannel.channel_id == channel_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    channels_skipped.append({
                        "title": title,
                        "username": username,
                        "channel_id": channel_id,
                        "subscriber_count": subscriber_count,
                        "reason": "Already exists"
                    })
                    logger.info(f"⏭️  Skipped: {title} (already exists)")
                    continue
                
                # Add new channel
                new_channel = TelegramChannel(
                    title=title,
                    username=username,
                    channel_id=channel_id,
                    is_active=True,
                    subscriber_count=subscriber_count,
                    notes="Auto-imported from subscriptions"
                )
                db.add(new_channel)
                await db.commit()
                await db.refresh(new_channel)
                
                channels_added.append({
                    "id": new_channel.id,
                    "title": title,
                    "username": username,
                    "channel_id": channel_id,
                    "subscriber_count": subscriber_count
                })
                logger.info(f"✅ Added: {title} ({subscriber_count:,} subscribers)" if subscriber_count else f"✅ Added: {title}")
                
            except Exception as e:
                await db.rollback()
                channels_failed.append({
                    "title": title,
                    "username": username,
                    "channel_id": channel_id,
                    "subscriber_count": subscriber_count,
                    "error": str(e)
                })
                logger.error(f"❌ Failed to add {title}: {e}")
        
        return {
            "success": True,
            "summary": {
                "added": len(channels_added),
                "skipped": len(channels_skipped),
                "failed": len(channels_failed)
            },
            "channels_added": channels_added,
            "channels_skipped": channels_skipped,
            "channels_failed": channels_failed
        }
        
    except Exception as e:
        logger.error(f"Error importing subscriptions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to import subscriptions: {str(e)}")


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
        # Get message statistics (averages)
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
        
        # Calculate medians using PostgreSQL's percentile_cont (more efficient than Python)
        from datetime import timedelta
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        
        # Median for all time
        median_query_all = select(
            func.percentile_cont(0.5).within_group(TelegramMessage.views).label('median_views_all'),
            func.percentile_cont(0.5).within_group(TelegramMessage.total_reactions).label('median_reactions'),
            func.percentile_cont(0.5).within_group(TelegramMessage.replies).label('median_comments'),
            func.percentile_cont(0.5).within_group(TelegramMessage.engagement_rate).label('median_engagement_rate'),
        ).where(TelegramMessage.channel_id == channel.id).where(
            TelegramMessage.views > 0
        )
        
        median_result_all = await db.execute(median_query_all)
        median_row_all = median_result_all.one()
        
        # Median for last 7 days
        median_query_7d = select(
            func.percentile_cont(0.5).within_group(TelegramMessage.views).label('median_views_7d'),
        ).where(TelegramMessage.channel_id == channel.id).where(
            TelegramMessage.views > 0
        ).where(
            TelegramMessage.date >= seven_days_ago
        )
        
        median_result_7d = await db.execute(median_query_7d)
        median_row_7d = median_result_7d.one_or_none()
        
        channel_stat = ChannelStats(
            channel_id=channel.id,
            channel_title=channel.title,
            is_active=channel.is_active,
            last_scraped_at=channel.last_scraped_at,
            subscriber_count=channel.subscriber_count,
            total_messages=stats_row.total_messages or 0,
            latest_message_date=stats_row.latest_message_date,
            avg_views=round(stats_row.avg_views, 2) if stats_row.avg_views else 0.0,
            avg_reactions=round(stats_row.avg_reactions, 2) if stats_row.avg_reactions else 0.0,
            avg_forwards=round(stats_row.avg_forwards, 2) if stats_row.avg_forwards else 0.0,
            avg_replies=round(stats_row.avg_replies, 2) if stats_row.avg_replies else 0.0,
            avg_engagement_count=round(stats_row.avg_engagement_count, 2) if stats_row.avg_engagement_count else 0.0,
            avg_engagement_rate=round(stats_row.avg_engagement_rate, 4) if stats_row.avg_engagement_rate else 0.0,
            # Real median calculations
            median_views=round(median_row_all.median_views_all, 2) if median_row_all.median_views_all else 0.0,
            median_views_7d=round(median_row_7d.median_views_7d, 2) if median_row_7d and median_row_7d.median_views_7d else 0.0,
            median_views_all_time=round(median_row_all.median_views_all, 2) if median_row_all.median_views_all else 0.0,
            median_reactions=round(median_row_all.median_reactions, 2) if median_row_all.median_reactions else 0.0,
            median_comments=round(median_row_all.median_comments, 2) if median_row_all.median_comments else 0.0,
            median_engagement_rate=round(median_row_all.median_engagement_rate, 4) if median_row_all.median_engagement_rate else 0.0,
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
# ADMIN/DIAGNOSTIC ENDPOINTS
# ============================================================================

@app.get("/admin/check-null-subscribers", tags=["Admin"])
async def check_null_subscriber_counts(db: AsyncSession = Depends(get_db)):
    """
    Check for channels with null subscriber_count.
    
    Returns statistics about how many channels have null subscriber counts
    and provides a list of affected channels.
    """
    try:
        # Count total channels
        total_query = select(func.count()).select_from(TelegramChannel)
        total_result = await db.execute(total_query)
        total_channels = total_result.scalar() or 0
        
        # Count channels with null subscriber_count
        null_query = select(func.count()).select_from(TelegramChannel).where(
            TelegramChannel.subscriber_count.is_(None)
        )
        null_result = await db.execute(null_query)
        null_count = null_result.scalar() or 0
        
        # Count channels with non-null subscriber_count
        not_null_count = total_channels - null_count
        
        # Get list of channels with null subscriber_count
        channels_query = select(TelegramChannel).where(
            TelegramChannel.subscriber_count.is_(None)
        )
        channels_result = await db.execute(channels_query)
        channels_with_null = channels_result.scalars().all()
        
        # Build channel list
        channels_list = [
            {
                "id": channel.id,
                "title": channel.title,
                "username": channel.username,
                "channel_id": channel.channel_id,
                "is_active": channel.is_active
            }
            for channel in channels_with_null
        ]
        
        percentage = (null_count / total_channels * 100) if total_channels > 0 else 0
        
        return {
            "success": True,
            "summary": {
                "total_channels": total_channels,
                "channels_with_subscriber_count": not_null_count,
                "channels_with_null_subscriber_count": null_count,
                "percentage_null": round(percentage, 2)
            },
            "channels_with_null": channels_list
        }
        
    except Exception as e:
        logger.error(f"Error checking null subscriber counts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check null subscriber counts: {str(e)}"
        )


@app.post("/admin/fix-null-subscribers", tags=["Admin"])
async def fix_null_subscriber_counts(db: AsyncSession = Depends(get_db)):
    """
    Fix NULL subscriber_count values by fetching from Telegram.
    
    This endpoint:
    1. Finds all channels with NULL subscriber_count
    2. Fetches the actual subscriber count from Telegram
    3. Updates the database with real values
    
    Note: This may take a while if there are many channels to update.
    """
    try:
        from scraper import client as telegram_client
        import asyncio
        
        # Connect to Telegram if not already connected
        if not telegram_client.is_connected():
            await telegram_client.connect()
            logger.info("✅ Connected to Telegram")
        
        # Find all channels with NULL subscriber_count
        query = select(TelegramChannel).where(
            TelegramChannel.subscriber_count.is_(None)
        )
        result = await db.execute(query)
        channels = result.scalars().all()
        
        total_channels = len(channels)
        logger.info(f"📊 Found {total_channels} channels with NULL subscriber_count")
        
        if total_channels == 0:
            return {
                "success": True,
                "message": "All channels already have subscriber counts!",
                "summary": {
                    "total_processed": 0,
                    "updated": 0,
                    "failed": 0
                }
            }
        
        updated_count = 0
        failed_count = 0
        updated_channels = []
        failed_channels = []
        
        for channel in channels:
            try:
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
                        
                        updated_channels.append({
                            "id": channel.id,
                            "title": channel.title,
                            "subscriber_count": subscriber_count
                        })
                        updated_count += 1
                        logger.info(f"✅ Updated {channel.title}: {subscriber_count:,} subscribers")
                    else:
                        failed_channels.append({
                            "id": channel.id,
                            "title": channel.title,
                            "reason": "Could not get subscriber count"
                        })
                        failed_count += 1
                
                except ValueError as e:
                    failed_channels.append({
                        "id": channel.id,
                        "title": channel.title,
                        "reason": f"Channel not found: {str(e)}"
                    })
                    failed_count += 1
                except Exception as e:
                    failed_channels.append({
                        "id": channel.id,
                        "title": channel.title,
                        "reason": str(e)
                    })
                    failed_count += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
            
            except Exception as e:
                logger.error(f"Error processing channel {channel.title}: {e}")
                failed_channels.append({
                    "id": channel.id,
                    "title": channel.title,
                    "reason": str(e)
                })
                failed_count += 1
                await db.rollback()
        
        return {
            "success": True,
            "message": f"Processed {total_channels} channels: {updated_count} updated, {failed_count} failed",
            "summary": {
                "total_processed": total_channels,
                "updated": updated_count,
                "failed": failed_count
            },
            "updated_channels": updated_channels,
            "failed_channels": failed_channels
        }
    
    except Exception as e:
        logger.error(f"Error fixing null subscriber counts: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix null subscriber counts: {str(e)}"
        )


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
    started_at = datetime.now(timezone.utc)
    
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
        
        completed_at = datetime.now(timezone.utc)
        
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
        completed_at = datetime.now(timezone.utc)
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

