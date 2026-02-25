import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CRYPTOCOMPARE_NEWS_URL = "https://min-api.cryptocompare.com/data/v2/news/"


class CryptoNewsService:
    """Free crypto news aggregator using CryptoCompare API (no key required)."""

    async def fetch_news(self, keywords: list[str], limit: int = 10) -> list[dict]:
        """Fetch latest crypto news articles, optionally filtered by keywords.

        CryptoCompare returns general crypto news.  We do a client-side keyword
        filter so that only articles mentioning the tracked tokens are kept.
        If nothing matches, we return top general headlines instead.
        """
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    CRYPTOCOMPARE_NEWS_URL,
                    params={"lang": "EN", "extraParams": "crypto-summary-bot"},
                )
                if resp.status_code != 200:
                    logger.warning(f"CryptoCompare news API returned {resp.status_code}")
                    return []

                data = resp.json()
                articles = data.get("Data", [])
                if not articles:
                    return []

                # Try to filter by keywords (case-insensitive)
                if keywords:
                    lower_kw = [k.lower() for k in keywords]
                    matched = [
                        a for a in articles
                        if any(
                            kw in (a.get("title", "") + " " + a.get("body", "")).lower()
                            for kw in lower_kw
                        )
                    ]
                    if matched:
                        return matched[:limit]

                # Fallback: return top general crypto headlines
                return articles[:limit]

        except Exception as e:
            logger.error(f"CryptoCompare news fetch failed: {e}")
            return []

    def format_news(self, articles: list[dict], coin_keywords: list[str] | None = None) -> str:
        """Format news articles into readable text for AI analysis."""
        if not articles:
            return "No crypto news available at this time."

        lines = ["Source: CryptoCompare News (free API)\n"]
        for i, article in enumerate(articles[:10]):
            title = article.get("title", "No title")
            source = article.get("source_info", {}).get("name", "") or article.get("source", "Unknown")
            url = article.get("url", "")
            body = article.get("body", "")

            # Truncate body for AI context
            if len(body) > 200:
                body = body[:200] + "..."

            lines.append(f"Article #{i+1}: {title}")
            lines.append(f"  Source: {source}")
            if body:
                lines.append(f"  Summary: {body}")
            if url:
                lines.append(f"  URL: {url}")
            lines.append("")

        return "\n".join(lines)
