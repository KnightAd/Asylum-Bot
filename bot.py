import asyncio
import logging
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import database
import scraper
from cogs.views import build_code_embed, build_active_codes_embed, GiftCodeActionView, LiveBoardView

import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("AsylumBot")

# Standard bot intents (Slash commands do not require privileged message content intent)
intents = discord.Intents.default()

class AsylumBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Called once before the bot connects to Discord."""
        # 1. Initialize SQLite Database
        await database.init_db()
        logger.info("Database initialized successfully.")

        # 2. Load Cogs
        await self.load_extension("cogs.codes")
        await self.load_extension("cogs.admin")
        logger.info("Loaded cogs: cogs.codes, cogs.admin")

        # 3. Start background periodic 2-hour scheduler loop
        if not self.auto_update_loop.is_running():
            self.auto_update_loop.change_interval(hours=config.CHECK_INTERVAL_HOURS)
            self.auto_update_loop.start()
            logger.info(f"Background code sync task scheduled every {config.CHECK_INTERVAL_HOURS} hour(s).")

        # 4. Global slash command error handler
        async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.MissingPermissions):
                missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
                msg = f"❌ You do not have permission to use this command.\nRequired permission: {missing}"
            elif isinstance(error, app_commands.BotMissingPermissions):
                missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
                msg = f"⚠️ The bot is missing required permissions to execute this: {missing}"
            elif isinstance(error, app_commands.CommandOnCooldown):
                msg = f"⏳ Command is on cooldown. Try again in {error.retry_after:.1f}s."
            else:
                logger.error(f"Error handling /{interaction.command.name if interaction.command else 'command'}: {error}", exc_info=error)
                msg = "⚠️ An unexpected error occurred while processing this command."

            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass

        self.tree.on_error = on_tree_error

    async def on_ready(self):
        """Called when bot is connected and ready."""
        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash command(s) globally.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")

        # Set bot presence
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=config.BOT_STATUS
        )
        await self.change_presence(status=discord.Status.online, activity=activity)

        logger.info("=" * 60)
        logger.info(f"🤖 Bot Logged In As: {self.user.name}#{self.user.discriminator} (ID: {self.user.id})")
        logger.info(f"🏰 Active Guilds: {len(self.guilds)}")
        logger.info(f"❄️ Whiteout Survival Auto-Sync: Every {config.CHECK_INTERVAL_HOURS} hours")
        logger.info("=" * 60)

    async def run_code_check_cycle(self) -> int:
        """
        Executes the scraping cycle:
        1. Scrapes active codes from online sources.
        2. Detects brand new codes and adds them to DB.
        3. Broadcasts new codes to each configured alliance channel with role pings.
        4. Updates the pinned 'Live Active Codes' board in all channels.
        Returns the count of newly detected codes.
        """
        logger.info("Starting automated gift code check cycle...")
        new_codes = []
        try:
            scraped_codes = await scraper.fetch_active_codes()
            logger.info(f"Scraper returned {len(scraped_codes)} active code candidates.")

            for item in scraped_codes:
                code_text = item["code"]
                existing = await database.get_code(code_text)
                if not existing:
                    # New code detected!
                    await database.add_gift_code(
                        code=code_text,
                        rewards=item.get("rewards", "In-game items & resources"),
                        expires_at=item.get("expires_at", "Limited Time"),
                        source=item.get("source", "Auto-Scraper")
                    )
                    new_codes.append(item)
                    logger.info(f"✨ Discovered NEW Gift Code: {code_text} | Rewards: {item.get('rewards')}")
                else:
                    # Ensure it is marked active
                    if not existing["is_active"]:
                        await database.set_code_status(code_text, True)

            # Sync active status: only codes currently on WoSTools remain active
            valid_active_names = [item["code"] for item in scraped_codes]
            await database.sync_active_codes(valid_active_names)

            # Announce new codes to all configured alliance servers
            if new_codes:
                await self.broadcast_new_codes(new_codes)

            # Refresh live active codes board across all servers
            await self.update_all_live_boards()

        except Exception as e:
            logger.error(f"Error during code check cycle: {e}", exc_info=True)

        return len(new_codes)

    async def broadcast_new_codes(self, codes: list[dict]):
        """Broadcasts newly detected codes to all configured alliance channels."""
        configured_guilds = await database.get_all_configured_guilds()
        for guild_data in configured_guilds:
            channel_id = guild_data.get("announcement_channel_id")
            if not channel_id:
                continue

            channel = self.get_channel(channel_id)
            if not channel:
                continue

            role_ping = ""
            if guild_data.get("alert_role_id"):
                role_ping = f"<@&{guild_data['alert_role_id']}> "

            for item in codes:
                try:
                    embed = build_code_embed(
                        code=item["code"],
                        rewards=item.get("rewards", "Gems & In-game items"),
                        expires_at=item.get("expires_at", "Limited Time"),
                        source=item.get("source", "Official")
                    )
                    view = GiftCodeActionView(item["code"])
                    await channel.send(
                        content=f"{role_ping}🚨 **New Official Whiteout Survival Gift Code!**",
                        embed=embed,
                        view=view
                    )
                except Exception as e:
                    logger.error(f"Failed to post code {item['code']} to channel {channel_id}: {e}")

    async def update_guild_live_board(self, guild_id: int):
        """Refreshes the pinned live board in a single guild."""
        settings = await database.get_guild_settings(guild_id)
        if not settings or not settings.get("announcement_channel_id"):
            return

        channel = self.get_channel(settings["announcement_channel_id"])
        if not channel:
            return

        active_codes = await database.get_active_codes()
        embed = build_active_codes_embed(active_codes, last_updated=datetime.utcnow())
        view = LiveBoardView()

        msg_id = settings.get("live_board_message_id")
        if msg_id:
            try:
                board_msg = await channel.fetch_message(msg_id)
                await board_msg.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                logger.info(f"Live board message {msg_id} was removed. Re-creating...")

        # If message not found or not created yet, post and pin a new one
        try:
            new_msg = await channel.send(embed=embed, view=view)
            try:
                await new_msg.pin(reason="Whiteout Survival Live Active Codes Board")
            except Exception:
                pass
            await database.set_guild_live_board(guild_id, new_msg.id)
        except Exception as e:
            logger.error(f"Failed to create live board in channel {channel.id}: {e}")

    async def update_all_live_boards(self):
        """Refreshes the live board in every configured guild."""
        configured_guilds = await database.get_all_configured_guilds()
        for guild_data in configured_guilds:
            await self.update_guild_live_board(guild_data["guild_id"])

    @tasks.loop(hours=config.CHECK_INTERVAL_HOURS)
    async def auto_update_loop(self):
        """Periodic background task that runs every 2 hours."""
        logger.info(f"⏰ Executing scheduled 2-hour code check...")
        await self.run_code_check_cycle()

    @auto_update_loop.before_loop
    async def before_auto_update_loop(self):
        """Wait until the bot is ready before starting the loop."""
        await self.wait_until_ready()

bot = AsylumBot()

def main():
    token = config.DISCORD_TOKEN
    if not token or token == "your_discord_bot_token_here":
        print("\n" + "=" * 70)
        print("❌ ERROR: Discord Bot Token is missing!")
        print("Please open the .env file in this directory and set:")
        print("DISCORD_TOKEN=your_token_from_discord_developer_portal")
        print("=" * 70 + "\n")
        return

    bot.run(token)

if __name__ == "__main__":
    main()
