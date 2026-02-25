import re
import feedparser
import httpx
import logging
from html import unescape
from typing import Optional

logger = logging.getLogger(__name__)

# Public Nitter instances with RSS support (fallback order)
DEFAULT_NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacyredirect.com",
    "https://xcancel.com",
    "https://nitter.space",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
]


class TwitterService:
    """Twitter/X feed reader using Nitter RSS (free, no API key needed)."""

    def __init__(self, nitter_instances: Optional[list[str]] = None):
        self.instances = nitter_instances or list(DEFAULT_NITTER_INSTANCES)

    async def search_tweets(self, queries: list[str], max_tweets: int = 20) -> list[dict]:
        """Search Twitter via Nitter RSS search feeds.

        Each query is turned into a Nitter search RSS URL.  The method
        tries multiple Nitter instances until one responds.
        """
        if not queries:
            return []

        all_entries: list[dict] = []
        per_query = max(max_tweets // max(len(queries), 1) + 1, 5)
        for query in queries[:5]:
            entries = await self._fetch_search_rss(query, limit=per_query)
            all_entries.extend(entries)

        # Deduplicate by link
        seen: set[str] = set()
        unique: list[dict] = []
        for entry in all_entries:
            key = entry.get("link", entry.get("text", ""))
            if key and key not in seen:
                seen.add(key)
                unique.append(entry)

        return unique[:max_tweets]

    async def _fetch_search_rss(self, query: str, limit: int = 10) -> list[dict]:
        """Fetch search results from Nitter RSS, trying instances in order."""
        rss_path = f"/search/rss?f=tweets&q={query}"

        for instance in self.instances:
            url = instance.rstrip("/") + rss_path
            try:
                entries = await self._parse_feed(url, limit)
                if entries:
                    logger.info(
                        f"Nitter RSS success: {instance} returned "
                        f"{len(entries)} results for '{query}'"
                    )
                    return entries
            except Exception as e:
                logger.debug(f"Nitter instance {instance} failed for '{query}': {e}")
                continue

        logger.warning(f"All Nitter instances failed for query '{query}'")
        return []

    async def fetch_user_timeline(self, username: str, limit: int = 10) -> list[dict]:
        """Fetch a user's timeline via Nitter RSS."""
        rss_path = f"/{username.lstrip('@')}/rss"

        for instance in self.instances:
            url = instance.rstrip("/") + rss_path
            try:
                entries = await self._parse_feed(url, limit)
                if entries:
                    logger.info(
                        f"Nitter RSS: got {len(entries)} tweets "
                        f"from @{username} via {instance}"
                    )
                    return entries
            except Exception as e:
                logger.debug(f"Nitter instance {instance} failed for @{username}: {e}")
                continue

        logger.warning(f"All Nitter instances failed for @{username}")
        return []

    async def _parse_feed(self, url: str, limit: int = 10) -> list[dict]:
        """Download and parse an RSS feed, returning normalised tweet dicts."""
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "CryptoSummaryBot/2.0"},
            )
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed parse error: {feed.bozo_exception}")

        results: list[dict] = []
        for entry in feed.entries[:limit]:
            # Clean HTML tags from summary/description
            raw_text = entry.get("summary") or entry.get("title") or ""
            clean_text = self._strip_html(unescape(raw_text))

            # Extract author from dc:creator or Nitter URL
            author = entry.get("author", "") or entry.get("dc_creator", "")
            if not author and "/" in entry.get("link", ""):
                parts = entry.get("link", "").split("/")
                for p in parts:
                    if p.startswith("@"):
                        author = p.lstrip("@")
                        break

            published = entry.get("published") or entry.get("updated") or ""

            results.append({
                "text": clean_text,
                "author": author,
                "link": entry.get("link", ""),
                "published": published,
                "title": entry.get("title", ""),
            })

        return results

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove HTML tags from text."""
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def format_tweets(self, tweets: list[dict]) -> str:
        """Format tweet data into readable text for AI analysis."""
        if not tweets:
            return "No Twitter/X social media data available."

        lines = ["Source: Twitter/X (via Nitter RSS)\n"]
        for i, tweet in enumerate(tweets[:15]):
            text = tweet.get("text") or tweet.get("title") or "N/A"
            author = tweet.get("author") or "Unknown"
            published = tweet.get("published") or "N/A"
            link = tweet.get("link", "")

            if len(text) > 200:
                text = text[:200] + "..."

            lines.append(f"Tweet #{i+1} by @{author} ({published}):")
            lines.append(f"  {text}")
            if link:
                lines.append(f"  Link: {link}")
            lines.append("")

        return "\n".join(lines)
