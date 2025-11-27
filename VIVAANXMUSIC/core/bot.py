import sys
import asyncio
from pyrogram import Client, errors
from pyrogram.enums import ChatMemberStatus

import config
from ..logging import LOGGER


class JARVIS(Client):
    def __init__(self):
        super().__init__(
            name="VivaanXMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            workers=48,
            max_concurrent_transmissions=7,
        )
        LOGGER(__name__).info("Bot client initialized.")

    async def start(self):
        await super().start()
        me = await self.get_me()
        self.username, self.id = me.username, me.id
        self.name = f"{me.first_name} {me.last_name or ''}".strip()
        self.mention = me.mention

        try:
            await self.send_message(
                config.LOGGER_ID,
                (
                    f"<u><b>» {self.mention} ʙᴏᴛ sᴛᴀʀᴛᴇᴅ :</b></u>\n\n"
                    f"ɪᴅ : de>{self.id}</code>\n"
                    f"ɴᴀᴍᴇ : {self.name}\n"
                    f"ᴜsᴇʀɴᴀᴍᴇ : @{self.username}"
                ),
            )
        except (errors.ChannelInvalid, errors.PeerIdInvalid):
            LOGGER(__name__).error("❌ Bot cannot access the log group/channel – add & promote it first!")
            sys.exit()
        except Exception as exc:
            LOGGER(__name__).error(f"❌ Bot has failed to access the log group.\nReason: {type(exc).__name__}")
            sys.exit()

        try:
            member = await self.get_chat_member(config.LOGGER_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).error("❌ Promote the bot as admin in the log group/channel.")
                sys.exit()
        except Exception as e:
            LOGGER(__name__).error(f"❌ Could not check admin status: {e}")
            sys.exit()

        # ====================================================================
        # SPATIAL AUDIO FEATURE - INITIALIZATION
        # ====================================================================
        try:
            from ..plugins.audio_tools.spatial.handler import (
                register_spatial_handlers,
                init_worker,
            )
            
            LOGGER(__name__).info("🎵 Initializing Spatial Audio feature...")
            
            # Register all spatial audio command handlers
            register_spatial_handlers(self)
            
            # Initialize background worker for audio processing
            await init_worker(self)
            
            LOGGER(__name__).info("✅ Spatial Audio feature loaded successfully!")
        
        except ImportError as e:
            LOGGER(__name__).warning(f"⚠️ Spatial Audio module not found: {e}")
        except Exception as e:
            LOGGER(__name__).error(f"❌ Error loading Spatial Audio: {e}")

        LOGGER(__name__).info(f"✅ Music Bot started as {self.name} (@{self.username})")
