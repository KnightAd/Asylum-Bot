import os
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

# Auto-update interval in hours (defaults to 2 hours)
try:
    CHECK_INTERVAL_HOURS = float(os.getenv("CHECK_INTERVAL_HOURS", "2"))
except ValueError:
    CHECK_INTERVAL_HOURS = 2.0

BOT_STATUS = os.getenv("BOT_STATUS", "Whiteout Survival | /codes")

# Parse hex color
raw_color = os.getenv("EMBED_COLOR", "0x2B88D9")
try:
    if raw_color.startswith("0x"):
        EMBED_COLOR = int(raw_color, 16)
    elif raw_color.startswith("#"):
        EMBED_COLOR = int(raw_color[1:], 16)
    else:
        EMBED_COLOR = int(raw_color, 16)
except ValueError:
    EMBED_COLOR = 0x2B88D9

WOS_REDEMPTION_URL = os.getenv("WOS_REDEMPTION_URL", "https://wos-giftcode.centurygame.com/")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frostcodes.db")
