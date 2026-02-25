import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEX_BASE = "https://api.dexscreener.com"


class DexScreenerService:
    """Client for DexScreener API (free, no key required)."""

    async def search_pairs(self, query: str) -> list[dict]:
        """Search for token pairs by query string."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{DEX_BASE}/latest/dex/search",
                    params={"q": query},
                )
                data = resp.json()
                return data.get("pairs", []) or []
        except Exception as e:
            logger.error(f"DexScreener search failed for '{query}': {e}")
            return []

    async def get_token_pairs(self, chain_id: str, token_address: str) -> list[dict]:
        """Get pairs for a specific token on a specific chain."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{DEX_BASE}/token-pairs/v1/{chain_id}/{token_address}",
                )
                data = resp.json()
                if isinstance(data, list):
                    return data
                return data.get("pairs", []) or []
        except Exception as e:
            logger.error(f"DexScreener token pairs failed: {e}")
            return []

    async def get_pair(self, chain_id: str, pair_address: str) -> Optional[dict]:
        """Get a specific pair by chain and pair address."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{DEX_BASE}/latest/dex/pairs/{chain_id}/{pair_address}",
                )
                data = resp.json()
                pairs = data.get("pairs", [])
                return pairs[0] if pairs else None
        except Exception as e:
            logger.error(f"DexScreener pair fetch failed: {e}")
            return None

    async def get_token_data(self, coin: dict) -> list[dict]:
        """Get best available DEX data for a coin config."""
        # If we have chain_id + token_address, use that
        if coin.get("chain_id") and coin.get("token_address"):
            pairs = await self.get_token_pairs(coin["chain_id"], coin["token_address"])
            if pairs:
                return pairs

        # Otherwise search by query
        query = coin.get("dex_search_query") or coin.get("symbol", "")
        pairs = await self.search_pairs(query)

        # Filter to find the most relevant pair
        symbol = coin.get("symbol", "").upper()
        relevant = [
            p for p in pairs
            if (p.get("baseToken", {}).get("symbol", "").upper() == symbol
                or symbol in p.get("baseToken", {}).get("name", "").upper())
        ]
        return relevant if relevant else pairs[:5]

    def format_pair_data(self, pairs: list[dict]) -> str:
        """Format DEX pair data into readable text."""
        if not pairs:
            return "No DexScreener data available"

        lines = ["Source: DexScreener\n"]
        for i, pair in enumerate(pairs[:3]):  # Top 3 pairs
            base = pair.get("baseToken", {})
            quote_token = pair.get("quoteToken", {})
            price_usd = pair.get("priceUsd", "N/A")
            price_change = pair.get("priceChange", {})
            volume = pair.get("volume", {})
            liquidity = pair.get("liquidity", {})
            txns = pair.get("txns", {})
            dex = pair.get("dexId", "Unknown DEX")
            chain = pair.get("chainId", "Unknown")
            pair_url = pair.get("url", "")

            h24_buys = txns.get("h24", {}).get("buys", 0)
            h24_sells = txns.get("h24", {}).get("sells", 0)
            h1_buys = txns.get("h1", {}).get("buys", 0)
            h1_sells = txns.get("h1", {}).get("sells", 0)

            lines.append(f"--- Pair #{i+1}: {base.get('symbol','?')}/{quote_token.get('symbol','?')} on {dex} ({chain}) ---")
            lines.append(f"Price USD: ${price_usd}")
            lines.append(f"Price change 5m: {price_change.get('m5', 'N/A')}%")
            lines.append(f"Price change 1h: {price_change.get('h1', 'N/A')}%")
            lines.append(f"Price change 6h: {price_change.get('h6', 'N/A')}%")
            lines.append(f"Price change 24h: {price_change.get('h24', 'N/A')}%")
            lines.append(f"Volume 24h: ${volume.get('h24', 0):,.2f}")
            lines.append(f"Volume 6h: ${volume.get('h6', 0):,.2f}")
            lines.append(f"Volume 1h: ${volume.get('h1', 0):,.2f}")
            lines.append(f"Liquidity USD: ${liquidity.get('usd', 0):,.2f}")
            lines.append(f"Txns 24h: {h24_buys} buys / {h24_sells} sells")
            lines.append(f"Txns 1h: {h1_buys} buys / {h1_sells} sells")
            lines.append(f"FDV: ${pair.get('fdv', 0):,.2f}")
            if pair_url:
                lines.append(f"URL: {pair_url}")
            lines.append("")

        return "\n".join(lines)
