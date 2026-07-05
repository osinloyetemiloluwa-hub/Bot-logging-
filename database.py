"""
Database models and management for Discord message logging
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "discord_logs.db")}')

# Handle Render's postgres:// vs postgresql:// prefix
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Message(Base):
    """Stores Discord messages"""
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)
    channel_id = Column(String(50), nullable=False, index=True)
    channel_name = Column(String(100), nullable=True)
    guild_id = Column(String(50), nullable=True, index=True)
    guild_name = Column(String(100), nullable=True)
    author_id = Column(String(50), nullable=False, index=True)
    author_name = Column(String(100), nullable=False)
    author_discriminator = Column(String(10), nullable=True)
    author_nickname = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    edited_timestamp = Column(DateTime, nullable=True)
    is_bot = Column(Boolean, default=False)
    is_system = Column(Boolean, default=False)
    mentions = Column(Text, nullable=True)
    mentioned_roles = Column(Text, nullable=True)
    has_attachments = Column(Boolean, default=False)
    has_embed = Column(Boolean, default=False)
    has_reactions = Column(Boolean, default=False)
    reply_to_message_id = Column(String(50), nullable=True, index=True)
    reply_to_author = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_channel_timestamp', 'channel_id', 'timestamp'),
        Index('idx_guild_timestamp', 'guild_id', 'timestamp'),
        Index('idx_author_timestamp', 'author_id', 'timestamp'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'guild_id': self.guild_id,
            'guild_name': self.guild_name,
            'author': {
                'id': self.author_id,
                'name': self.author_name,
                'discriminator': self.author_discriminator,
                'nickname': self.author_nickname,
                'is_bot': self.is_bot
            },
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'edited_timestamp': self.edited_timestamp.isoformat() if self.edited_timestamp else None,
            'mentions': self.mentions,
            'mentioned_roles': self.mentioned_roles,
            'has_attachments': self.has_attachments,
            'has_embed': self.has_embed,
            'has_reactions': self.has_reactions,
            'reply_to_message_id': self.reply_to_message_id,
            'reply_to_author': self.reply_to_author,
        }


class Attachment(Base):
    __tablename__ = 'attachments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), ForeignKey('messages.message_id'), nullable=False, index=True)
    attachment_id = Column(String(50), nullable=True)
    filename = Column(String(500), nullable=True)
    content_type = Column(String(100), nullable=True)
    url = Column(String(1000), nullable=False)
    size = Column(Integer, nullable=True)
    proxy_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'attachment_id': self.attachment_id,
            'filename': self.filename,
            'content_type': self.content_type,
            'url': self.url,
            'size': self.size,
            'proxy_url': self.proxy_url
        }


class EditedMessage(Base):
    __tablename__ = 'edited_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), ForeignKey('messages.message_id'), nullable=False, index=True)
    old_content = Column(Text, nullable=True)
    new_content = Column(Text, nullable=True)
    edited_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'old_content': self.old_content,
            'new_content': self.new_content,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None
        }


class DeletedMessage(Base):
    __tablename__ = 'deleted_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)
    channel_id = Column(String(50), nullable=False, index=True)
    channel_name = Column(String(100), nullable=True)
    guild_id = Column(String(50), nullable=True)
    guild_name = Column(String(100), nullable=True)
    author_id = Column(String(50), nullable=False)
    author_name = Column(String(100), nullable=False)
    author_discriminator = Column(String(10), nullable=True)
    content = Column(Text, nullable=True)
    original_timestamp = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, default=datetime.utcnow, index=True)
    has_attachments = Column(Boolean, default=False)
    reply_to_message_id = Column(String(50), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'guild_id': self.guild_id,
            'guild_name': self.guild_name,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'content': self.content,
            'original_timestamp': self.original_timestamp.isoformat() if self.original_timestamp else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'has_attachments': self.has_attachments,
            'reply_to_message_id': self.reply_to_message_id
        }


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get a new database session. Caller MUST close it."""
    return SessionLocal()


def close_db(db):
    """Close database session"""
    if db:
        db.close()
