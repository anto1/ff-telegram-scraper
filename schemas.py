"""
Pydantic schemas for API request/response validation.

Provides type-safe data validation and serialization for FastAPI endpoints.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# CHANNEL SCHEMAS
# ============================================================================

class ChannelCreate(BaseModel):
    """Schema for creating a new channel."""
    title: str = Field(..., min_length=1, max_length=255, description="Human-readable channel name")
    username: Optional[str] = Field(None, max_length=255, description="Telegram @username (optional)")
    channel_id: int = Field(..., description="Telegram channel ID (required, must be unique)")
    is_active: bool = Field(True, description="Whether to scrape this channel")
    notes: Optional[str] = Field(None, description="Optional notes about the channel")


class ChannelUpdate(BaseModel):
    """Schema for updating an existing channel. All fields are optional."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    username: Optional[str] = Field(None, max_length=255)
    channel_id: Optional[int] = None
    is_active: Optional[bool] = None
    color_flag: Optional[int] = None
    notes: Optional[str] = None


class ColorFlagUpdate(BaseModel):
    """Schema for updating channel color flag."""
    color_flag: int = Field(..., description="Color flag/category number for frontend display")


class ChannelResponse(BaseModel):
    """Schema for channel in API responses."""
    id: int
    title: str
    username: Optional[str]
    channel_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_scraped_at: Optional[datetime]
    subscriber_count: Optional[int]
    color_flag: Optional[int]
    notes: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)


class ChannelWithStats(BaseModel):
    """Schema for channel with additional statistics."""
    id: int
    title: str
    username: Optional[str]
    channel_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_scraped_at: Optional[datetime]
    subscriber_count: Optional[int]
    color_flag: Optional[int]
    notes: Optional[str]
    
    # Statistics (added dynamically)
    messages_count: int = 0
    latest_message_date: Optional[datetime] = None
    avg_engagement_rate: Optional[float] = None
    avg_views: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# MESSAGE SCHEMAS
# ============================================================================

class MessageResponse(BaseModel):
    """Schema for message in API responses."""
    id: int
    channel_id: int
    message_id: int
    date: Optional[datetime]
    text: Optional[str]
    views: Optional[int]
    forwards: Optional[int]
    replies: Optional[int]
    total_reactions: Optional[int]
    engagement_count: Optional[int]
    engagement_rate: Optional[float]
    post_length: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# STATS SCHEMAS
# ============================================================================

class ChannelStats(BaseModel):
    """Detailed statistics for a single channel."""
    channel_id: int
    channel_title: str
    is_active: bool
    last_scraped_at: Optional[datetime]
    subscriber_count: Optional[int] = None
    
    # Message counts
    total_messages: int
    latest_message_date: Optional[datetime]
    
    # Engagement metrics (averages/medians)
    avg_views: Optional[float] = 0.0
    avg_reactions: Optional[float] = 0.0
    avg_forwards: Optional[float] = 0.0
    avg_replies: Optional[float] = 0.0
    avg_engagement_count: Optional[float] = 0.0
    avg_engagement_rate: Optional[float] = 0.0
    
    # Median values (more robust to outliers)
    median_views: Optional[float] = 0.0
    median_views_7d: Optional[float] = 0.0
    median_views_all_time: Optional[float] = 0.0
    median_reactions: Optional[float] = 0.0
    median_comments: Optional[float] = 0.0
    median_engagement_rate: Optional[float] = 0.0


class GlobalStats(BaseModel):
    """Global statistics across all channels."""
    total_channels: int
    active_channels: int
    total_messages: int
    last_scrape_time: Optional[datetime]


# ============================================================================
# SCRAPER SCHEMAS
# ============================================================================

class ScrapeRequest(BaseModel):
    """Request to trigger scraping."""
    channel_ids: Optional[list[int]] = Field(
        None, 
        description="Specific channel IDs to scrape. If None, scrapes all active channels."
    )
    limit: int = Field(
        200, 
        ge=1, 
        le=1000, 
        description="Maximum number of messages to fetch per channel"
    )


class ScrapeResponse(BaseModel):
    """Response from scraping operation."""
    success: bool
    channels_processed: int
    total_messages_scraped: int
    errors: list[str] = []
    started_at: datetime
    completed_at: datetime


# ============================================================================
# AUTHENTICATION SCHEMAS
# ============================================================================

class AuthStartRequest(BaseModel):
    """Schema for starting Telegram authentication."""
    phone_number: str = Field(..., description="Phone number with country code (e.g., +1234567890)")


class AuthStartResponse(BaseModel):
    """Schema for authentication start response."""
    success: bool
    message: str
    phone_code_hash: Optional[str] = None


class AuthVerifyRequest(BaseModel):
    """Schema for verifying Telegram authentication code."""
    phone_number: str = Field(..., description="Phone number used in auth start")
    code: str = Field(..., description="Verification code received via Telegram")
    phone_code_hash: str = Field(..., description="Hash received from auth start")


class AuthVerifyResponse(BaseModel):
    """Schema for authentication verification response."""
    success: bool
    message: str
    user_info: Optional[dict] = None


