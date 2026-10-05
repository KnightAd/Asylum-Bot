import discord
from discord import ui
from datetime import datetime
from config import EMBED_COLOR, WOS_REDEMPTION_URL

def build_code_embed(code: str, rewards: str, expires_at: str = "Limited Time", source: str = "Official", is_active: bool = True) -> discord.Embed:
    """Build a rich Whiteout Survival themed embed for an individual code announcement."""
    status_icon = "🟢 Active" if is_active else "🔴 Expired"
    embed = discord.Embed(
        title=f"❄️ Whiteout Survival — Gift Code: {code}",
        description=(
            f"**Tap or double-click to copy:**\n"
            f"```{code}```\n"
            f"🎁 **Rewards:** {rewards}\n"
            f"⏳ **Status:** {status_icon} ({expires_at})\n"
            f"📡 **Source:** {source}\n"
        ),
        color=EMBED_COLOR if is_active else 0x95A5A6,
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url="https://wos-giftcode.centurygame.com/favicon.ico")
    embed.set_footer(text="Asylum Bot • Auto-refreshes every 2 hours")
    return embed

def build_active_codes_embed(codes: list[dict], last_updated: datetime | None = None) -> discord.Embed:
    """Build the comprehensive active codes board embed."""
    embed = discord.Embed(
        title="❄️ Whiteout Survival — Live Active Gift Codes",
        description=(
            "Here are the currently active official gift codes for Whiteout Survival.\n"
            "Tap any code below to select/copy it, or use the **Redeem on Web** button.\n"
            "*(This board automatically refreshes every 2 hours)*\n"
        ),
        color=EMBED_COLOR,
        timestamp=last_updated or datetime.utcnow()
    )
    
    if not codes:
        embed.add_field(
            name="No Active Codes Found",
            value="There are no active codes known at the moment. The bot will automatically announce new codes as soon as they drop!",
            inline=False
        )
    else:
        for idx, item in enumerate(codes[:20], 1):
            code_text = item['code']
            rewards_text = item.get('rewards') or 'In-game items & resources'
            expires_text = item.get('expires_at') or 'Limited Time'
            embed.add_field(
                name=f"{idx}. 🎁 `{code_text}`",
                value=f"• **Rewards:** {rewards_text}\n• **Expires:** {expires_text}",
                inline=False
            )
            
    embed.set_footer(text="Asylum Bot • Live Board")
    return embed

class HowToRedeemModal(ui.View):
    """View containing quick guidance on how to redeem codes."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Button(label="Open Official Web Portal", url=WOS_REDEMPTION_URL, style=discord.ButtonStyle.link, emoji="🌐"))

class GiftCodeActionView(ui.View):
    """Interactive action buttons attached to individual code announcements."""
    def __init__(self, code: str):
        super().__init__(timeout=None)
        self.code = code
        self.add_item(ui.Button(label="Redeem on Web", url=WOS_REDEMPTION_URL, style=discord.ButtonStyle.link, emoji="🌐"))

    @ui.button(label="Copy Code", style=discord.ButtonStyle.primary, emoji="📋")
    async def copy_button(self, interaction: discord.Interaction, button: ui.Button):
        """Sends an ephemeral plain-text block for clean 1-click copying."""
        await interaction.response.send_message(
            f"```{self.code}```\n*(Long-press or select above to copy code directly)*",
            ephemeral=True
        )

    @ui.button(label="How to Redeem", style=discord.ButtonStyle.secondary, emoji="📖")
    async def redeem_help_button(self, interaction: discord.Interaction, button: ui.Button):
        """Shows instructions for Android and iOS."""
        guide_text = (
            "### 🎮 How to Redeem in Whiteout Survival\n\n"
            "**🤖 Android Users:**\n"
            "1. Open Whiteout Survival.\n"
            "2. Tap your **Chief Avatar** (top-left).\n"
            "3. Tap **Settings** (gear icon) ➔ **Gift Code**.\n"
            "4. Paste the code and tap **Redeem**.\n\n"
            "**🍎 iOS & PC Users:**\n"
            "1. Find your **Player ID** (under your avatar in-game).\n"
            f"2. Visit the [Official Gift Code Center]({WOS_REDEMPTION_URL}).\n"
            "3. Enter your **Player ID** and the **Gift Code**.\n"
            "4. Check your in-game mailbox to collect your rewards!"
        )
        await interaction.response.send_message(guide_text, ephemeral=True)

class LiveBoardView(ui.View):
    """Persistent buttons attached to the pinned Live Active Codes Board."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.Button(label="Redeem on Web", url=WOS_REDEMPTION_URL, style=discord.ButtonStyle.link, emoji="🌐"))

    @ui.button(label="How to Redeem", style=discord.ButtonStyle.secondary, emoji="📖")
    async def how_to_redeem(self, interaction: discord.Interaction, button: ui.Button):
        guide_text = (
            "### 🎮 How to Redeem in Whiteout Survival\n\n"
            "**🤖 Android Users:**\n"
            "1. Open Whiteout Survival.\n"
            "2. Tap your **Chief Avatar** (top-left).\n"
            "3. Tap **Settings** (gear icon) ➔ **Gift Code**.\n"
            "4. Paste the code and tap **Redeem**.\n\n"
            "**🍎 iOS & PC Users:**\n"
            "1. Find your **Player ID** (under your avatar in-game).\n"
            f"2. Visit the [Official Gift Code Center]({WOS_REDEMPTION_URL}).\n"
            "3. Enter your **Player ID** and the **Gift Code**.\n"
            "4. Check your in-game mailbox to collect your rewards!"
        )
        await interaction.response.send_message(guide_text, ephemeral=True)
