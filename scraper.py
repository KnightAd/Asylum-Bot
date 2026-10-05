import re
import logging
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("WOSScraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Known rewards catalog for Whiteout Survival codes
KNOWN_REWARDS = {
    "THXTEACHER": "1000 Gems, 5x 5m Speedup, 2x Gold Key, 5x 100K Meat, 5x 100K Wood",
    "GAECHEONJEOL": "500 Gems, 10x 5m Speedup, 10K Hero XP, 1x Mythic Shard",
    "GUDOKYTKOR": "500 Gems, 10x 5m Speedup, 1x Gold Key",
    "2NDYOUTUBEKR": "300 Gems, 5x 5m Speedup, 50K Hero XP",
    "1STYOUTUBEKR": "300 Gems, 5x 5m Speedup, 50K Hero XP",
    "GOGOWOS": "10K Hero XP, 2x Gold Keys, 5x 100 Gems, 20x 5m General Speedup"
}

async def fetch_html(url: str, session: aiohttp.ClientSession) -> str | None:
    """Fetch HTML content from a URL safely."""
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Failed to fetch {url}, status code: {resp.status}")
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
    return None

def parse_wostools(html: str) -> list[dict]:
    """
    Parses active gift codes directly from wostools.net/gift-codes.
    Looks specifically for .known-code-item containers marked as 'active'.
    """
    results = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.find_all("div", class_=lambda c: c and "known-code-item" in c and "active" in c)
        
        for item in items:
            text_el = item.find(class_=lambda c: c and "known-code-text" in c)
            status_el = item.find(class_=lambda c: c and "known-code-status" in c)
            
            if not text_el:
                continue
                
            code_text = text_el.get_text(strip=True)
            status_text = status_el.get_text(strip=True) if status_el else "Active"
            
            # Verify code is active and valid format
            if "Active" in status_text and code_text and 3 <= len(code_text) <= 35:
                clean_code = code_text.strip()
                upper_key = clean_code.upper()
                rewards = KNOWN_REWARDS.get(upper_key, "Gems, Speedups, Gold Keys & Hero Resources")
                
                results.append({
                    "code": clean_code,
                    "rewards": rewards,
                    "expires_at": "Active Now",
                    "source": "WoSTools"
                })
                
        logger.info(f"Parsed {len(results)} active code(s) from WoSTools.")
    except Exception as e:
        logger.error(f"Error parsing WoSTools: {e}")
    return results

async def fetch_active_codes() -> list[dict]:
    """
    Scrapes https://wostools.net/gift-codes as the authoritative active gift code source.
    Returns only verified, active codes.
    """
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Primary authoritative source: WoSTools
        wos_html = await fetch_html("https://wostools.net/gift-codes", session)
        if wos_html:
            active_codes = parse_wostools(wos_html)
            if active_codes:
                return active_codes
                
    # Fallback to empty if network issue occurs
    return []
