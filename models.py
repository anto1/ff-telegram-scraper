"""
SQLAlchemy ORM models for Telegram scraper database.

Tables:
- telegram_channels: Configuration and metadata for channels to scrape
- telegram_messages: Scraped messages with engagement metrics
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, 
    ForeignKey, BigInteger, Float, Index, JSON
)
from sqlalchemy.orm import relationship
from db import Base


# Timezone-aware datetime helper
def utcnow():
    return datetime.now(timezone.utc)


class TelegramChannel(Base):
    """
    Telegram channel configuration.
    
    Stores channels to scrape and their metadata.
    Supports soft delete via is_active flag.
    """
    __tablename__ = "telegram_channels"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Channel identification
    title = Column(String(255), nullable=False, index=True, comment="Human-readable channel name")
    username = Column(String(255), nullable=True, index=True, comment="Telegram @username (optional)")
    channel_id = Column(BigInteger, nullable=False, unique=True, index=True, comment="Telegram channel ID (required)")
    
    # Status and timestamps
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="Whether to scrape this channel")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, comment="When channel was added")
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False, comment="Last update time")
    last_scraped_at = Column(DateTime(timezone=True), nullable=True, comment="Last successful scrape timestamp")
    
    # Channel statistics
    subscriber_count = Column(Integer, nullable=True, comment="Number of channel subscribers/members")
    
    # Color flag for frontend categorization
    color_flag = Column(Integer, nullable=True, comment="Color flag/category for frontend display (0-N)")
    
    # Optional metadata
    notes = Column(Text, nullable=True, comment="Optional notes about this channel")
    
    # Relationship to messages (one-to-many)
    messages = relationship("TelegramMessage", back_populates="channel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<TelegramChannel(id={self.id}, title='{self.title}', channel_id={self.channel_id})>"


class TelegramMessage(Base):
    """
    Scraped Telegram message with engagement metrics.
    
    Stores individual posts from channels with all their metrics.
    Uses UPSERT logic based on (channel_id, message_id) to avoid duplicates.
    """
    __tablename__ = "telegram_messages"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to channel
    channel_id = Column(Integer, ForeignKey("telegram_channels.id"), nullable=False, index=True)
    
    # Telegram message identification
    message_id = Column(BigInteger, nullable=False, comment="Telegram message ID within the channel")
    
    # Message metadata
    date = Column(DateTime(timezone=True), nullable=True, comment="When message was posted on Telegram")
    text = Column(Text, nullable=True, comment="Full message text")
    
    # Engagement metrics
    views = Column(Integer, nullable=True, comment="Total views")
    forwards = Column(Integer, nullable=True, default=0, comment="Number of times forwarded")
    replies = Column(Integer, nullable=True, default=0, comment="Number of replies/comments")
    total_reactions = Column(Integer, nullable=True, default=0, comment="Total free reactions (excludes paid)")
    
    # Calculated metrics
    engagement_count = Column(Integer, nullable=True, default=0, comment="Total interactions (reactions + forwards + replies)")
    engagement_rate = Column(Float, nullable=True, default=0.0, comment="Engagement percentage (engagement/views * 100)")
    post_length = Column(Integer, nullable=True, default=0, comment="Character count of post text")
    
    # Raw data storage (optional, for future reference)
    raw_json = Column(JSON, nullable=True, comment="Full Telegram message object as JSON")
    
    # Timestamp
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, comment="When we first saved this message")
    
    # Relationship to channel
    channel = relationship("TelegramChannel", back_populates="messages")
    
    # Composite unique constraint and indexes
    __table_args__ = (
        Index('idx_channel_message', 'channel_id', 'message_id', unique=True),
        Index('idx_date', 'date'),
        Index('idx_engagement_rate', 'engagement_rate'),
        Index('idx_engagement_count', 'engagement_count'),
    )
    
    def __repr__(self):
        return f"<TelegramMessage(id={self.id}, channel_id={self.channel_id}, message_id={self.message_id})>"

