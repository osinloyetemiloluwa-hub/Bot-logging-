import discord
from discord import Intents
from datetime import datetime
import json
import logging
import os
import threading
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask import Flask, request, jsonify, g
from flask_cors import CORS

# ============ DATABASE ============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "discord_logs.db")}')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)
    channel_id = Column(String(50), nullable=False, index=True)
    channel_name = Column(String(100), nullable=True)
    guild_id = Column(String(50), nullable=True, index=True)
    guild_name = Column(String(100), nullable=True)
    author_id = Column(String(50), nullable=False, index=True)
    author_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_deleted = Column(Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'channel_name': self.channel_name,
            'guild_name': self.guild_name,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_deleted': self.is_deleted
        }

class DeletedMessage(Base):
    __tablename__ = 'deleted_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(50), unique=True, nullable=False, index=True)
    channel_id = Column(String(50), nullable=False, index=True)
    channel_name = Column(String(100), nullable=True)
    guild_id = Column(String(50), nullable=True)
    author_id = Column(String(50), nullable=False)
    author_name = Column(String(100), nullable=False)
    content = Column(Text, nullable=True)
    original_timestamp = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'content': self.content,
            'original_timestamp': self.original_timestamp.isoformat() if self.original_timestamp else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None
        }

Base.metadata.create_all(bind=engine)

# ============ LOGGING ============
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# ============ FLASK API ============
app = Flask(__name__)
CORS(app)

def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Discord Logger API'})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    db = get_db()
    try:
        query = db.query(Message).filter(Message.is_deleted == False)
        if request.args.get('channel_id'):
            query = query.filter(Message.channel_id == request.args.get('channel_id'))
        if request.args.get('search'):
            query = query.filter(Message.content.like(f"%{request.args.get('search')}%"))
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 100)), 1000)
        messages = query.limit(limit).all()
        return jsonify({'success': True, 'count': len(messages), 'messages': [m.to_dict() for m in messages]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deleted', methods=['GET'])
def get_deleted_messages():
    db = get_db()
    try:
        messages = db.query(DeletedMessage).order_by(DeletedMessage.deleted_at.desc()).limit(100).all()
        return jsonify({'success': True, 'count': len(messages), 'deleted_messages': [m.to_dict() for m in messages]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    try:
        total = db.query(func.count(Message.id)).filter(Message.is_deleted == False).scalar()
        deleted = db.query(func.count(DeletedMessage.id)).scalar()
        return jsonify({'success': True, 'stats': {'total_messages': total, 'total_deleted': deleted}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DISCORD BOT ============
class MessageLoggerBot(discord.Client):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        super().__init__(intents=intents)

    async def on_ready(self):
        logger.info(f'Bot logged in as {self.user} | Servers: {len(self.guilds)}')

    async def on_message(self, message):
        if message.author.bot:
            return
        db = SessionLocal()
        try:
            msg = Message(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                content=message.content,
                timestamp=message.created_at,
                is_bot=message.author.bot
            )
            db.add(msg)
            db.commit()
            logger.info(f'Logged: {message.id}')
        except Exception as e:
            logger.error(f'Error: {e}')
            db.rollback()
        finally:
            db.close()

    async def on_message_delete(self, message):
        db = SessionLocal()
        try:
            msg_record = db.query(Message).filter_by(message_id=str(message.id)).first()
            deleted = DeletedMessage(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                content=message.content,
                original_timestamp=message.created_at
            )
            db.add(deleted)
            if msg_record:
                msg_record.content = "[DELETED]"
                msg_record.is_deleted = True
            db.commit()
            logger.info(f'Deleted: {message.id}')
        except Exception as e:
            logger.error(f'Error: {e}')
            db.rollback()
        finally:
            db.close()

def run_bot():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('DISCORD_TOKEN not set!')
        return
    bot = MessageLoggerBot()
    bot.run(token)

# ============ RUN BOTH ============
if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()

    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
