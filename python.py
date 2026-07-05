"""
Discord Bot - Message Logger
Logs messages, edits, deletes, attachments, and replies to SQLite database
"""

import discord
from discord import Intents
from datetime import datetime
import json
import logging
import os
from database import Message, Attachment, EditedMessage, DeletedMessage, get_db, close_db, init_db
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MessageLoggerBot(discord.Client):
    """Discord bot that logs all messages to database"""

    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        intents.reactions = True
        super().__init__(intents=intents)

    async def on_ready(self):
        logger.info(f'Bot logged in as {self.user}')
        logger.info(f'Bot ID: {self.user.id}')
        logger.info(f'Total servers: {len(self.guilds)}')
        logger.info('Bot is ready and listening for messages!')

    async def on_message(self, message):
        if message.author.bot:
            return
        if message.type != discord.MessageType.default:
            return

        db = get_db()
        try:
            mentioned_users = [str(m.id) for m in message.mentions]
            mentioned_roles = [str(r.id) for r in message.role_mentions]

            reply_to_message_id = None
            reply_to_author = None
            if message.reference and message.reference.message_id:
                try:
                    referenced_msg = await message.channel.fetch_message(message.reference.message_id)
                    reply_to_message_id = str(referenced_msg.id)
                    reply_to_author = str(referenced_msg.author)
                except:
                    reply_to_message_id = str(message.reference.message_id)

            msg_record = Message(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                author_discriminator=getattr(message.author, 'discriminator', '0'),
                author_nickname=getattr(message.author, 'nick', None),
                content=message.content if message.content else None,
                timestamp=message.created_at,
                is_bot=message.author.bot,
                mentions=json.dumps(mentioned_users) if mentioned_users else None,
                mentioned_roles=json.dumps(mentioned_roles) if mentioned_roles else None,
                has_attachments=len(message.attachments) > 0,
                has_embed=len(message.embeds) > 0,
                has_reactions=len(message.reactions) > 0,
                reply_to_message_id=reply_to_message_id,
                reply_to_author=reply_to_author
            )
            db.add(msg_record)

            for attachment in message.attachments:
                att_record = Attachment(
                    message_id=str(message.id),
                    attachment_id=str(attachment.id),
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    url=attachment.url,
                    size=attachment.size,
                    proxy_url=attachment.proxy_url
                )
                db.add(att_record)

            db.commit()
            logger.info(f'Logged message {message.id} from {message.author}')

        except Exception as e:
            logger.error(f'Error logging message: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)

    async def on_message_edit(self, before, after):
        if before.content == after.content:
            return
        if after.type != discord.MessageType.default:
            return

        db = get_db()
        try:
            msg_record = db.query(Message).filter_by(message_id=str(after.id)).first()
            if msg_record:
                msg_record.content = after.content
                msg_record.edited_timestamp = discord.utils.utcnow()

                edit_record = EditedMessage(
                    message_id=str(after.id),
                    old_content=before.content,
                    new_content=after.content,
                    edited_at=discord.utils.utcnow()
                )
                db.add(edit_record)
                db.commit()
                logger.info(f'Logged edit for message {after.id}')
        except Exception as e:
            logger.error(f'Error logging message edit: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)

    async def on_message_delete(self, message):
        if message.type != discord.MessageType.default:
            return

        db = get_db()
        try:
            msg_record = db.query(Message).filter_by(message_id=str(message.id)).first()

            deleted_record = DeletedMessage(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                author_discriminator=getattr(message.author, 'discriminator', '0'),
                content=message.content,
                original_timestamp=message.created_at,
                has_attachments=len(message.attachments) > 0,
                reply_to_message_id=msg_record.reply_to_message_id if msg_record else None
            )
            db.add(deleted_record)

            if msg_record:
                msg_record.content = "[MESSAGE DELETED]"

            db.commit()
            logger.info(f'Logged deletion of message {message.id}')

        except Exception as e:
            logger.error(f'Error logging message deletion: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)


def run_bot(token: str):
    init_db()
    logger.info('Database initialized')
    
    bot = MessageLoggerBot()
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f'Bot crashed: {e}')
        logger.error(traceback.format_exc())
        raise


if __name__ == '__main__':
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    if not DISCORD_TOKEN:
        logger.error('DISCORD_TOKEN not found! Please set it in environment variables')
        exit(1)

    run_bot(DISCORD_TOKEN)
