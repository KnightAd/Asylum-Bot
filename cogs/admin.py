import discord
from discord import app_commands
from discord.ext import commands
import database
from cogs.views import build_code_embed, build_active_codes_embed, GiftCodeActionView, LiveBoardView

class AdminCog(commands.Cog, name="Admin"):
    """Leadership and management commands for configuring channels, roles, and codes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setchannel", description="Set the alliance channel for gift code announcements and live board.")
    @app_commands.describe(channel="The text channel where gift codes will be posted (e.g. #gift-codes)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Sets the announcement channel and initializes the pinned Live Active Codes board."""
        await interaction.response.defer(ephemeral=True)
        
        # Save channel to DB
        await database.set_guild_channel(interaction.guild_id, channel.id)

        # Create the initial Live Board message in the chosen channel
        active_codes = await database.get_active_codes()
        embed = build_active_codes_embed(active_codes)
        view = LiveBoardView()

        try:
            board_msg = await channel.send(embed=embed, view=view)
            try:
                await board_msg.pin(reason="Whiteout Survival Live Active Codes Board")
            except Exception:
                pass  # Pinned limits or missing pin permissions
            
            await database.set_guild_live_board(interaction.guild_id, board_msg.id)
            await interaction.followup.send(
                f"✅ Announcement channel set to {channel.mention}!\n"
                f"📌 A live active codes board has been posted and pinned in {channel.mention}. "
                "The bot will automatically update it every 2 hours!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ Channel was saved, but the bot lacks permission to send messages or pin in {channel.mention}. "
                "Please grant the bot `Send Messages`, `Embed Links`, and `Manage Messages` (for pinning).",
                ephemeral=True
            )

    @app_commands.command(name="setrole", description="Set or clear the role pinged when new gift codes drop.")
    @app_commands.describe(role="Role to ping (leave empty to disable pings)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setrole_cmd(self, interaction: discord.Interaction, role: discord.Role = None):
        """Configures the alert role for new codes."""
        role_id = role.id if role else None
        await database.set_guild_role(interaction.guild_id, role_id)

        if role:
            await interaction.response.send_message(
                f"✅ Alert role set to {role.mention}. Members with this role will be pinged when new codes arrive!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "✅ Alert role cleared. New codes will now be posted without pinging a role.",
                ephemeral=True
            )

    @app_commands.command(name="addcode", description="Manually add and publish a new official gift code.")
    @app_commands.describe(
        code="The gift code (e.g. WOS123)",
        rewards="Rewards included in this code (e.g. 500 Gems, 10x Speedup)",
        expires="Expiration date or notes (default: Limited Time)",
        announce="Broadcast to the announcement channel immediately? (default: True)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def addcode_cmd(
        self,
        interaction: discord.Interaction,
        code: str,
        rewards: str = "In-game items & resources",
        expires: str = "Limited Time",
        announce: bool = True
    ):
        """Manually registers a code into database and broadcasts to alliance."""
        clean_code = code.strip().upper()
        is_new = await database.add_gift_code(clean_code, rewards, expires, source=f"Manual ({interaction.user.name})")

        reply_text = f"✅ Code `{clean_code}` saved to database!"
        if not is_new:
            reply_text = f"ℹ️ Code `{clean_code}` was already in the database and has been refreshed/marked active."

        await interaction.response.send_message(reply_text, ephemeral=True)

        # Trigger announcement and live board refresh if requested
        if announce:
            settings = await database.get_guild_settings(interaction.guild_id)
            if settings and settings.get("announcement_channel_id"):
                channel = self.bot.get_channel(settings["announcement_channel_id"])
                if channel:
                    role_mention = ""
                    if settings.get("alert_role_id"):
                        role_mention = f"<@&{settings['alert_role_id']}> "
                    
                    embed = build_code_embed(clean_code, rewards, expires, source=f"Manual ({interaction.user.name})")
                    view = GiftCodeActionView(clean_code)
                    await channel.send(
                        content=f"{role_mention}🚨 **New Whiteout Survival Gift Code Available!**",
                        embed=embed,
                        view=view
                    )

            # Update live board
            await self.bot.update_guild_live_board(interaction.guild_id)

    @app_commands.command(name="expirecode", description="Mark a gift code as expired.")
    @app_commands.describe(code="The code to mark expired")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def expirecode_cmd(self, interaction: discord.Interaction, code: str):
        """Marks a code as expired and refreshes the live board."""
        clean_code = code.strip().upper()
        success = await database.set_code_status(clean_code, False)

        if success:
            await interaction.response.send_message(f"✅ Code `{clean_code}` marked as expired.", ephemeral=True)
            await self.bot.update_guild_live_board(interaction.guild_id)
        else:
            await interaction.response.send_message(f"❌ Code `{clean_code}` was not found in the database.", ephemeral=True)

    @app_commands.command(name="deletecode", description="Completely delete a code from the database.")
    @app_commands.describe(code="The code to delete")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def deletecode_cmd(self, interaction: discord.Interaction, code: str):
        """Deletes a code permanently."""
        clean_code = code.strip().upper()
        success = await database.delete_code(clean_code)

        if success:
            await interaction.response.send_message(f"🗑️ Code `{clean_code}` deleted.", ephemeral=True)
            await self.bot.update_guild_live_board(interaction.guild_id)
        else:
            await interaction.response.send_message(f"❌ Code `{clean_code}` was not found.", ephemeral=True)

    @app_commands.command(name="checknow", description="Force an immediate check for new gift codes now.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def checknow_cmd(self, interaction: discord.Interaction):
        """Manually runs the 2-hour scraper check immediately."""
        await interaction.response.defer(ephemeral=True)
        new_count = await self.bot.run_code_check_cycle()
        await interaction.followup.send(
            f"🔄 Code check completed!\n"
            f"Found **{new_count}** new active code(s). All alliance live boards have been updated.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
