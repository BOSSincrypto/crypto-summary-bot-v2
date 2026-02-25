import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CMC_BASE = "https://pro-api.coinmarketcap.com"


class CoinMarketCapService:
    """Client for CoinMarketCap API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "X-CMC_PRO_API_KEY": api_key,
            "Accept": "application/json",
        }

    async def get_quote(self, symbol: str) -> Optional[dict]:
        """Get latest quote for a cryptocurrency symbol."""
        if not self.api_key:
            logger.warning("CoinMarketCap API key not configured")
            return None
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{CMC_BASE}/v1/cryptocurrency/quotes/latest",
                    headers=self.headers,
                    params={"symbol": symbol.upper(), "convert": "USD"},
                )
                data = resp.json()
                if data.get("status", {}).get("error_code") == 0:
                    coin_data = data.get("data", {}).get(symbol.upper())
                    if isinstance(coin_data, list):
                        return coin_data[0] if coin_data else None
                    return coin_data
                else:
                    logger.warning(f"CMC API error for {symbol}: {data.get('status', {}).get('error_message')}")
                    return None
        except Exception as e:
            logger.error(f"CMC API request failed for {symbol}: {e}")
            return None

    async def get_quotes_batch(self, symbols: list[str]) -> dict:
        """Get quotes for multiple symbols at once."""
        if not self.api_key:
            return {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{CMC_BASE}/v1/cryptocurrency/quotes/latest",
                    headers=self.headers,
                    params={"symbol": ",".join(s.upper() for s in symbols), "convert": "USD"},
                )
                data = resp.json()
                if data.get("status", {}).get("error_code") == 0:
                    return data.get("data", {})
                return {}
        except Exception as e:
            logger.error(f"CMC batch request failed: {e}")
            return {}

    def format_quote(self, quote: dict) -> str:
        """Format a CMC quote into readable text."""
        if not quote:
            return "No CoinMarketCap data available"

        usd = quote.get("quote", {}).get("USD", {})
        name = quote.get("name", "Unknown")
        symbol = quote.get("symbol", "?")
        price = usd.get("price", 0)
        change_1h = usd.get("percent_change_1h", 0)
        change_24h = usd.get("percent_change_24h", 0)
        change_7d = usd.get("percent_change_7d", 0)
        volume_24h = usd.get("volume_24h", 0)
        market_cap = usd.get("market_cap", 0)

        return (
            f"Source: CoinMarketCap\n"
            f"Name: {name} ({symbol})\n"
            f"Price: ${price:,.8f}\n"
            f"Change 1h: {change_1h:+.2f}%\n"
            f"Change 24h: {change_24h:+.2f}%\n"
            f"Change 7d: {change_7d:+.2f}%\n"
            f"Volume 24h: ${volume_24h:,.2f}\n"
            f"Market Cap: ${market_cap:,.2f}"
        )
