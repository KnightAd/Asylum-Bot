import aiosqlite
from datetime import datetime
from config import DB_PATH

async def init_db():
    """Initialize SQLite database tables if they do not exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                rewards TEXT DEFAULT 'Rewards not specified',
                expires_at TEXT DEFAULT 'Limited Time',
                is_active INTEGER DEFAULT 1,
                added_at TEXT NOT NULL,
                source TEXT DEFAULT 'Auto-Scraper'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                announcement_channel_id INTEGER,
                alert_role_id INTEGER,
                live_board_message_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS member_profiles (
                user_id INTEGER PRIMARY KEY,
                player_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()

async def add_gift_code(code: str, rewards: str = "In-game items & resources", expires_at: str = "Limited Time", source: str = "Auto-Scraper") -> bool:
    """
    Inserts a new gift code. Returns True if code was added, False if it already existed.
    """
    clean_code = code.strip().upper()
    now_iso = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO gift_codes (code, rewards, expires_at, is_active, added_at, source)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (clean_code, rewards, expires_at, now_iso, source))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Code already exists, ensure it's marked active if re-added
            await db.execute("""
                UPDATE gift_codes
                SET is_active = 1, rewards = COALESCE(NULLIF(?, ''), rewards)
                WHERE code = ?
            """, (rewards, clean_code))
            await db.commit()
            return False

async def get_active_codes() -> list[dict]:
    """Retrieve all currently active gift codes."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT code, rewards, expires_at, is_active, added_at, source
            FROM gift_codes
            WHERE is_active = 1
            ORDER BY added_at DESC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_all_codes() -> list[dict]:
    """Retrieve all codes (active and expired)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT code, rewards, expires_at, is_active, added_at, source
            FROM gift_codes
            ORDER BY is_active DESC, added_at DESC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_code(code: str) -> dict | None:
    """Retrieve a single code by its name."""
    clean_code = code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT code, rewards, expires_at, is_active, added_at, source
            FROM gift_codes
            WHERE code = ?
        """, (clean_code,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def set_code_status(code: str, is_active: bool) -> bool:
    """Set active status (1 for active, 0 for expired)."""
    clean_code = code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            UPDATE gift_codes
            SET is_active = ?
            WHERE code = ?
        """, (1 if is_active else 0, clean_code))
        await db.commit()
        return cursor.rowcount > 0

async def sync_active_codes(valid_active_codes: list[str]):
    """
    Syncs the database with authoritative active codes from WoSTools.
    Ensures codes not in valid_active_codes are marked inactive (0).
    """
    clean_valid = [c.strip().upper() for c in valid_active_codes]
    async with aiosqlite.connect(DB_PATH) as db:
        if clean_valid:
            placeholders = ",".join("?" for _ in clean_valid)
            # Mark all non-manual codes NOT in this list as expired
            await db.execute(f"""
                UPDATE gift_codes
                SET is_active = 0
                WHERE UPPER(code) NOT IN ({placeholders})
                  AND (source LIKE '%Scraper%' OR source LIKE '%WoSTools%' OR source LIKE '%PocketGamer%' OR source LIKE '%Beebom%')
            """, clean_valid)
            # Ensure valid ones are marked active
            await db.execute(f"""
                UPDATE gift_codes
                SET is_active = 1
                WHERE UPPER(code) IN ({placeholders})
            """, clean_valid)
        else:
            await db.execute("""
                UPDATE gift_codes
                SET is_active = 0
                WHERE source LIKE '%Scraper%' OR source LIKE '%WoSTools%'
            """)
        await db.commit()

async def delete_code(code: str) -> bool:
    """Delete a code permanently."""
    clean_code = code.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            DELETE FROM gift_codes WHERE code = ?
        """, (clean_code,))
        await db.commit()
        return cursor.rowcount > 0

# Guild Settings Methods

async def get_guild_settings(guild_id: int) -> dict | None:
    """Get settings for a specific guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT guild_id, announcement_channel_id, alert_role_id, live_board_message_id
            FROM guild_settings
            WHERE guild_id = ?
        """, (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_configured_guilds() -> list[dict]:
    """Get all guilds with an announcement channel configured."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT guild_id, announcement_channel_id, alert_role_id, live_board_message_id
            FROM guild_settings
            WHERE announcement_channel_id IS NOT NULL
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def set_guild_channel(guild_id: int, channel_id: int):
    """Set the announcement channel for a guild."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, announcement_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET announcement_channel_id = excluded.announcement_channel_id
        """, (guild_id, channel_id))
        await db.commit()

async def set_guild_role(guild_id: int, role_id: int | None):
    """Set or clear the alert role to ping on new codes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, alert_role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET alert_role_id = excluded.alert_role_id
        """, (guild_id, role_id))
        await db.commit()

async def set_guild_live_board(guild_id: int, message_id: int | None):
    """Save the message ID of the pinned live active codes board."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO guild_settings (guild_id, live_board_message_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET live_board_message_id = excluded.live_board_message_id
        """, (guild_id, message_id))
        await db.commit()

# Member Profiles

async def save_member_id(user_id: int, player_id: str):
    """Save or update user's in-game Player ID."""
    clean_id = player_id.strip()
    now_iso = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO member_profiles (user_id, player_id, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET player_id = excluded.player_id, updated_at = excluded.updated_at
        """, (user_id, clean_id, now_iso))
        await db.commit()

async def get_member_id(user_id: int) -> str | None:
    """Retrieve saved in-game Player ID for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT player_id FROM member_profiles WHERE user_id = ?
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
