import discord
from discord import app_commands
from discord.ext import commands
import database
from cogs.views import build_code_embed, build_active_codes_embed, GiftCodeActionView, LiveBoardView, HowToRedeemModal
from config import WOS_REDEMPTION_URL, EMBED_COLOR

class CodesCog(commands.Cog, name="Codes"):
    """User-facing commands for viewing and redeeming gift codes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="codes", description="Show all currently active Whiteout Survival gift codes.")
    async def codes_cmd(self, interaction: discord.Interaction):
        """Displays all active gift codes in an interactive embed."""
        await interaction.response.defer()
        active_codes = await database.get_active_codes()
        embed = build_active_codes_embed(active_codes)
        view = LiveBoardView()
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="code", description="Look up details and rewards for a specific gift code.")
    @app_commands.describe(code="The gift code to look up (e.g. gogoWOS)")
    async def code_cmd(self, interaction: discord.Interaction, code: str):
        """Shows details for a specific code."""
        await interaction.response.defer()
        clean_code = code.strip().upper()
        data = await database.get_code(clean_code)

        if data:
            embed = build_code_embed(
                code=data["code"],
                rewards=data["rewards"],
                expires_at=data["expires_at"],
                source=data["source"],
                is_active=bool(data["is_active"])
            )
            view = GiftCodeActionView(data["code"])
            await interaction.followup.send(embed=embed, view=view)
        else:
            embed = discord.Embed(
                title=f"❄️ Code: {clean_code}",
                description=(
                    f"Code `{clean_code}` was not found in the active database.\n"
                    "It may be brand new or already expired. You can still test it directly on the official portal below!"
                ),
                color=EMBED_COLOR
            )
            view = GiftCodeActionView(clean_code)
            await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="redeem", description="Instructions and direct link to redeem gift codes.")
    async def redeem_cmd(self, interaction: discord.Interaction):
        """Step-by-step guide to redeeming codes."""
        embed = discord.Embed(
            title="🎁 How to Redeem Whiteout Survival Gift Codes",
            description=(
                "Follow these steps to claim your gifts:\n\n"
                "### 🤖 Android (In-Game)\n"
                "1. Tap your **Chief Avatar** in the top left.\n"
                "2. Tap **Settings** ➔ **Gift Code**.\n"
                "3. Enter the code and tap **Redeem**.\n\n"
                "### 🍎 iOS & PC (Web Portal)\n"
                "1. Find your **Player ID** under your Avatar profile in-game.\n"
                f"2. Open the [Official Gift Code Center]({WOS_REDEMPTION_URL}).\n"
                "3. Type your **Player ID** and the **Gift Code**.\n"
                "4. Check your in-game mailbox for the rewards!"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text="Tip: Use /myid to save your Player ID with the bot!")
        view = HowToRedeemModal()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="myid", description="Save your in-game Player ID for quick reference.")
    @app_commands.describe(player_id="Your in-game Whiteout Survival Player ID (found under your avatar)")
    async def myid_cmd(self, interaction: discord.Interaction, player_id: str):
        """Saves member Player ID to database."""
        clean_id = player_id.strip()
        await database.save_member_id(interaction.user.id, clean_id)
        
        embed = discord.Embed(
            title="✅ Player ID Saved",
            description=(
                f"Successfully saved your Whiteout Survival Player ID:\n"
                f"```{clean_id}```\n"
                f"Use `/getid` anytime to retrieve it or copy it for web redemption!"
            ),
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="getid", description="Retrieve your saved Whiteout Survival Player ID.")
    async def getid_cmd(self, interaction: discord.Interaction):
        """Retrieves member's saved Player ID."""
        saved_id = await database.get_member_id(interaction.user.id)
        if saved_id:
            embed = discord.Embed(
                title="🆔 Your Saved Whiteout Survival Player ID",
                description=(
                    f"**Tap or double-click to copy:**\n"
                    f"```{saved_id}```\n"
                    f"Use this on the [Official Redemption Portal]({WOS_REDEMPTION_URL})!"
                ),
                color=EMBED_COLOR
            )
            view = HowToRedeemModal()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ You haven't saved a Player ID yet! Use `/myid <your_id>` to save it.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(CodesCog(bot))
