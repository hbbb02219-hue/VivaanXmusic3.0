"""
Spatial Audio Handler - VivaanXMusic 3.0
Telegram command handlers for /spatialize, /cinema, /maxwide, etc.
"""

import logging
import asyncio
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler

from VIVAANXMUSIC.utils.audio.engine import SpatializeEngine
from VIVAANXMUSIC.utils.audio.cache import AudioCache
from VIVAANXMUSIC.utils.audio.worker import AudioWorker
from VIVAANXMUSIC.utils.audio.presets import (
    list_presets, 
    get_preset_help,
    PRESETS
)
from VIVAANXMUSIC.utils.audio.config import (
    MAX_FILE_SIZE,
    MAX_DURATION,
    MIN_DURATION,
    USER_MAX_CONCURRENT,
    USER_RATE_LIMIT_ENABLED,
    AUDIO_CACHE_DIR,
    AVAILABLE_PRESETS,
)

logger = logging.getLogger(__name__)

# Global instances
engine = SpatializeEngine()
cache = AudioCache()
worker = AudioWorker(max_concurrent=2)

# Track per-user request counts and processing
user_requests = {}
user_processing = {}


class SpatialAudioHandler:
    """Handler for spatial audio commands"""
    
    @staticmethod
    def _check_rate_limit(user_id: int) -> bool:
        """Check if user exceeded rate limit"""
        if not USER_RATE_LIMIT_ENABLED:
            return True
        
        now = datetime.now()
        
        # Initialize per-user request tracking
        if user_id not in user_requests:
            user_requests[user_id] = []
        
        # Remove old requests (>1 hour)
        cutoff = now - timedelta(hours=1)
        user_requests[user_id] = [
            req_time for req_time in user_requests[user_id]
            if req_time > cutoff
        ]
        
        # Check limit (max 10 per hour)
        if len(user_requests[user_id]) >= 10:
            return False
        
        # Check concurrent processing (max 2)
        if user_id not in user_processing:
            user_processing[user_id] = 0
        
        if user_processing[user_id] >= USER_MAX_CONCURRENT:
            return False
        
        # Add this request
        user_requests[user_id].append(now)
        return True
    
    @staticmethod
    async def _validate_audio(message: Message) -> Optional[tuple]:
        """
        Validate audio file and return (file_path, duration, channels)
        Returns None if validation fails
        """
        audio_file = message.audio or message.document or message.video or message.voice
        
        if not audio_file:
            await message.reply_text(
                "❌ **No audio file found**\n\n"
                "Please send an audio file (MP3, WAV, M4A, FLAC, OGG, etc.)"
            )
            return None
        
        # Check file size
        file_size = audio_file.file_size or 0
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ **File too large**\n\n"
                f"Max size: {MAX_FILE_SIZE / (1024*1024):.0f} MB\n"
                f"Your file: {file_size / (1024*1024):.1f} MB"
            )
            return None
        
        # Download file
        try:
            logger.info(f"📥 Downloading audio from user {message.from_user.id}...")
            file_path = await message.download(file_name=None)
            
            if not file_path:
                await message.reply_text("❌ Failed to download audio file")
                return None
            
            file_path = Path(file_path)
            
            # Get audio info
            sr, channels, duration = engine.get_audio_info(file_path)
            
            if sr == 0:
                file_path.unlink(missing_ok=True)
                await message.reply_text("❌ Invalid audio file format")
                return None
            
            # Check duration
            if duration > MAX_DURATION:
                file_path.unlink(missing_ok=True)
                await message.reply_text(
                    f"❌ **Audio too long**\n\n"
                    f"Max duration: {MAX_DURATION}s ({MAX_DURATION//60}m)\n"
                    f"Your audio: {duration:.0f}s ({duration/60:.1f}m)"
                )
                return None
            
            if duration < MIN_DURATION:
                file_path.unlink(missing_ok=True)
                await message.reply_text(
                    f"❌ **Audio too short**\n\n"
                    f"Minimum: {MIN_DURATION} seconds"
                )
                return None
            
            logger.info(f"✅ Audio validated: {duration:.1f}s, {channels}ch, {sr}Hz")
            return file_path, duration, channels
        
        except Exception as e:
            logger.error(f"Error validating audio: {e}")
            await message.reply_text(f"❌ **Error processing file:**\n`{e}`")
            return None
    
    @staticmethod
    async def _process_spatialize(
        client: Client,
        message: Message,
        preset_name: str = "cinema"
    ):
        """Process spatialize command"""
        
        user_id = message.from_user.id
        
        # Rate limit check
        if not SpatialAudioHandler._check_rate_limit(user_id):
            await message.reply_text(
                "⏰ **Rate limit exceeded**\n\n"
                "Max: 10 requests per hour\n"
                "Max: 2 concurrent processes\n\n"
                "Try again later!"
            )
            return
        
        # Validate audio
        result = await SpatialAudioHandler._validate_audio(message)
        if not result:
            return
        
        input_path, duration, channels = result
        
        try:
            # Get preset
            if preset_name not in PRESETS:
                input_path.unlink(missing_ok=True)
                await message.reply_text(
                    f"❌ **Unknown preset: {preset_name}**\n\n"
                    + list_presets(),
                    parse_mode="markdown"
                )
                return
            
            preset = PRESETS[preset_name]
            
            # Send initial status
            status_msg = await message.reply_text(
                f"🎵 **Processing Audio**\n\n"
                f"Preset: **{preset.name}**\n"
                f"Duration: `{duration:.1f}s`\n"
                f"Channels: `{channels}`\n\n"
                f"⏳ Starting..."
            )
            
            # Create task ID
            task_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
            
            # Prepare output path
            output_dir = AUDIO_CACHE_DIR / "processed"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{task_id}_{preset_name}.mp3"
            
            # Read input file for caching
            try:
                with open(input_path, 'rb') as f:
                    file_data = f.read()
            except Exception as e:
                logger.error(f"Error reading file: {e}")
                await status_msg.edit_text(
                    f"❌ **Error reading file:**\n`{e}`"
                )
                input_path.unlink(missing_ok=True)
                return
            
            # Check cache
            cached_path = await cache.get(file_data, preset_name)
            if cached_path and cached_path.exists():
                logger.info(f"Using cached result for {task_id}")
                
                await status_msg.edit_text(
                    "✅ **Processing Complete!**\n\n"
                    "📦 _From cache (instant)_"
                )
                
                try:
                    await message.reply_audio(
                        audio=str(cached_path),
                        title=f"Spatialized - {preset.name}",
                        performer=message.from_user.first_name or "VivaanXMusic",
                    )
                except Exception as e:
                    logger.error(f"Error sending cached audio: {e}")
                    await message.reply_text(f"❌ Error sending file: {e}")
                
                input_path.unlink(missing_ok=True)
                return
            
            # Increment user processing counter
            user_processing[user_id] = user_processing.get(user_id, 0) + 1
            
            # Create callback for task completion
            async def task_callback(task):
                nonlocal user_id, status_msg, input_path, file_data, preset_name
                
                user_processing[user_id] = max(0, user_processing.get(user_id, 0) - 1)
                
                try:
                    if task.status == "completed":
                        await status_msg.edit_text(
                            "✅ **Processing Complete!**\n\n"
                            f"⏱️ Time: `{task.result['duration']:.1f}s`\n"
                            f"📊 Size: `{task.result['output_size'] / 1024:.1f}KB`"
                        )
                        
                        # Cache result
                        await cache.set(file_data, preset_name, task.output_path)
                        
                        # Send file
                        try:
                            await message.reply_audio(
                                audio=str(task.output_path),
                                title=f"Spatialized - {preset.name}",
                                performer=message.from_user.first_name or "VivaanXMusic",
                            )
                        except Exception as e:
                            logger.error(f"Error sending audio: {e}")
                            await message.reply_text(f"❌ Error sending audio: {e}")
                    
                    elif task.status == "failed":
                        error_msg = task.error or "Unknown error"
                        await status_msg.edit_text(
                            f"❌ **Processing Failed**\n\n"
                            f"`{error_msg}`"
                        )
                
                except Exception as e:
                    logger.error(f"Error in callback: {e}")
                
                finally:
                    # Cleanup input file
                    input_path.unlink(missing_ok=True)
            
            # Enqueue task
            success = await worker.enqueue(
                task_id=task_id,
                user_id=user_id,
                input_path=input_path,
                output_path=output_path,
                preset=preset_name,
                callback=task_callback,
            )
            
            if not success:
                user_processing[user_id] = max(0, user_processing.get(user_id, 0) - 1)
                await status_msg.edit_text("❌ **Queue full**. Try again later!")
                input_path.unlink(missing_ok=True)
                return
            
            logger.info(f"Task enqueued: {task_id} for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error in spatialize handler: {e}")
            await message.reply_text(f"❌ **Error:**\n`{e}`")
            input_path.unlink(missing_ok=True)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

async def cmd_spatialize(client: Client, message: Message):
    """Handle /spatialize command"""
    args = message.command
    preset = "cinema"
    
    if len(args) > 1:
        preset = args[1].lower()
        if preset not in PRESETS:
            await message.reply_text(
                f"❌ **Unknown preset: {preset}**\n\n"
                + list_presets(),
                parse_mode="markdown"
            )
            return
    
    await SpatialAudioHandler._process_spatialize(client, message, preset)


async def cmd_preset_specific(client: Client, message: Message, preset_name: str):
    """Handle preset-specific commands like /cinema, /maxwide, etc"""
    await SpatialAudioHandler._process_spatialize(client, message, preset_name)


async def cmd_help(client: Client, message: Message):
    """Handle /spatialize_help command"""
    help_text = f"""
🎵 **Spatial Audio Help**

**Commands:**
• `/spatialize [preset]` - Convert audio to 3D spatial (binaural)
• `/cinema` - Cinema preset shortcut
• `/maxwide` - MaxWide preset shortcut
• `/bassboost` - BassBoost preset shortcut
• `/spatialize_help` - Show this help
• `/spatialize_stats` - Show system stats

**Available Presets:**
{list_presets()}

{get_preset_help()}

**Examples:**
• `/spatialize` - Use default (cinema) preset
• `/spatialize cinema [audio]` - Explicit preset
• `/cinema [audio]` - Direct command

**Limits:**
• Max file: {MAX_FILE_SIZE / (1024*1024):.0f} MB
• Max duration: {MAX_DURATION}s ({MAX_DURATION//60}m)
• Max 10 requests/hour
• Max 2 concurrent

**Tips:**
🎧 Best with headphones!
📱 Works with MP3, WAV, M4A, FLAC, OGG
⚡ Results are cached for 24 hours
    """
    
    await message.reply_text(help_text, parse_mode="markdown")


async def cmd_stats(client: Client, message: Message):
    """Show worker and cache statistics"""
    worker_stats = worker.get_queue_stats()
    cache_stats = cache.get_cache_stats()
    user_tasks = worker.get_user_tasks(message.from_user.id)
    
    stats_text = f"""
📊 **System Statistics**

**Processing Queue:**
• Active tasks: `{worker_stats['active_tasks']}`
• Queue size: `{worker_stats['queue_size']}`
• Completed: `{worker_stats['completed']}`
• Failed: `{worker_stats['failed']}`
• Avg time: `{worker_stats['avg_processing_time']:.1f}s`

**Cache Status:**
• Files: `{cache_stats['total_files']}`
• Used: `{cache_stats['total_size_mb']} MB / {cache_stats['max_size_mb']} MB`
• Usage: `{cache_stats['usage_percent']}%`

**Your Tasks:**
• Active: `{len([t for t in user_tasks if t.status in ['queued', 'processing']])}`
• Completed: `{len([t for t in user_tasks if t.status == 'completed'])}`
• Total: `{len(user_tasks)}`
    """
    
    await message.reply_text(stats_text, parse_mode="markdown")


# ============================================================================
# HANDLER REGISTRATION
# ============================================================================

def register_spatial_handlers(app: Client):
    """Register all spatial audio handlers"""
    
    try:
        # Main commands
        app.add_handler(
            MessageHandler(cmd_spatialize, filters.command("spatialize")),
            group=10
        )
        
        app.add_handler(
            MessageHandler(cmd_help, filters.command("spatialize_help")),
            group=10
        )
        
        app.add_handler(
            MessageHandler(cmd_stats, filters.command("spatialize_stats")),
            group=10
        )
        
        # Preset-specific commands
        for preset_name in AVAILABLE_PRESETS:
            app.add_handler(
                MessageHandler(
                    lambda c, m, p=preset_name: cmd_preset_specific(c, m, p),
                    filters.command(preset_name)
                ),
                group=10
            )
        
        logger.info("✅ Spatial Audio handlers registered successfully!")
    
    except Exception as e:
        logger.error(f"❌ Error registering handlers: {e}")


async def init_worker(app: Client):
    """Initialize background worker"""
    try:
        await worker.start()
        # Start processing loop
        asyncio.create_task(worker.process_worker(engine))
        logger.info("✅ Audio worker initialized")
    except Exception as e:
        logger.error(f"❌ Error initializing worker: {e}")
