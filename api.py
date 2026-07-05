"""
Discord Logger API - Flask REST API
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import logging
from database import Message, Attachment, EditedMessage, DeletedMessage, SessionLocal, init_db

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db:
        db.close()

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Discord Logger API',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/')
def index():
    return jsonify({
        'service': 'Discord Logger API',
        'endpoints': [
            '/api/health',
            '/api/messages',
            '/api/messages/<message_id>',
            '/api/channels',
            '/api/stats'
        ]
    })

@app.route('/api/messages', methods=['GET'])
def get_messages():
    db = get_db()
    try:
        query = db.query(Message)
        
        if request.args.get('channel_id'):
            query = query.filter(Message.channel_id == request.args.get('channel_id'))
        if request.args.get('guild_id'):
            query = query.filter(Message.guild_id == request.args.get('guild_id'))
        if request.args.get('author_id'):
            query = query.filter(Message.author_id == request.args.get('author_id'))
        
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        
        messages = query.all()
        return jsonify({
            'success': True,
            'count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels', methods=['GET'])
def get_channels():
    db = get_db()
    try:
        from sqlalchemy import func
        channels = db.query(
            Message.channel_id,
            Message.channel_name,
            Message.guild_id,
            Message.guild_name,
            func.count(Message.id).label('message_count')
        ).group_by(Message.channel_id).all()
        
        return jsonify({
            'success': True,
            'channels': [{
                'channel_id': c.channel_id,
                'channel_name': c.channel_name,
                'guild_id': c.guild_id,
                'guild_name': c.guild_name,
                'message_count': c.message_count
            } for c in channels]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    db = get_db()
    try:
        from sqlalchemy import func
        total_messages = db.query(func.count(Message.id)).scalar()
        total_users = db.query(func.count(func.distinct(Message.author_id))).scalar()
        total_channels = db.query(func.count(func.distinct(Message.channel_id))).scalar()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_messages': total_messages or 0,
                'total_users': total_users or 0,
                'total_channels': total_channels or 0,
                'generated_at': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/messages/<message_id>', methods=['GET'])
def get_message(message_id):
    db = get_db()
    try:
        message = db.query(Message).filter_by(message_id=message_id).first()
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        return jsonify({'success': True, 'message': message.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
