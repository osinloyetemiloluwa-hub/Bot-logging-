"""
Discord Bot + API combined - runs both in one service
"""

import discord
from discord import Intents
from datetime import datetime
import json
import logging
import os
import threading
from database import Message, Attachment, EditedMessage, DeletedMessage, get_db, close_db, init_db

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, timedelta
from sqlalchemy import func

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
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
    return jsonify({
        'status': 'healthy',
        'service': 'Discord Logger API',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/messages', methods=['GET'])
def get_messages():
    db = get_db()
    try:
        query = db.query(Message)
        if request.args.get('channel_id'):
            query = query.filter(Message.channel_id == request.args.get('channel_id'))
        if request.args.get('search'):
            query = query.filter(Message.content.like(f"%{request.args.get('search')}%"))
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))
        messages = query.limit(limit).offset(offset).all()
        return jsonify({
            'success': True,
            'count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/deleted', methods=['GET'])
def get_deleted_messages():
    db = get_db()
    try:
        messages = db.query(DeletedMessage).order_by(DeletedMessage.deleted_at.desc()).limit(100).all()
        return jsonify({
            'success': True,
            'count': len(messages),
            'deleted_messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    try:
        total = db.query(func.count(Message.id)).scalar()
        deleted = db.query(func.count(DeletedMessage.id)).scalar()
        return jsonify({
            'success': True,
            'stats': {'total_messages': total, 'total_deleted': deleted}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============ DISCORD BOT ============
class MessageLoggerBot(discord.Client):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)

    async def on_ready(self):
        logger.info(f'Bot logged in as {self.user}')
        logger.info(f'Servers: {len(self.guilds)}')

    async def on_message(self, message):
        if message.author.bot:
            return
        db = get_db()
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
                is_bot=message.author.bot,
                has_attachments=len(message.attachments) > 0
            )
            db.add(msg)
            db.commit()
            logger.info(f'Logged message {message.id}')
        except Exception as e:
            logger.error(f'Error: {e}')
            db.rollback()
        finally:
            close_db(db)

    async def on_message_delete(self, message):
        db = get_db()
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
                msg_record.content = "[MESSAGE DELETED]"
            db.commit()
        except Exception as e:
            logger.error(f'Error: {e}')
            db.rollback()
        finally:
            close_db(db)

# ============ RUN BOTH ============
def run_bot():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error('DISCORD_TOKEN not set!')
        return
    bot = MessageLoggerBot()
    bot.run(token)

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    init_db()
    
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start Flask API (this keeps the service alive)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
