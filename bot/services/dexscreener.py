import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEX_BASE = "https://api.dexscreener.com"

# Stablecoins to filter for USD-denominated pairs
USD_QUOTE_SYMBOLS = {"USDC", "USDT", "DAI", "BUSD", "USDbC", "USD+"}


class DexScreenerService:
    """Client for DexScreener API (free, no key required).

    Filters pairs to USD/USDC quotes and sorts by liquidity (largest pools first).
    """

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

    @staticmethod
    def _filter_usd_pairs(pairs: list[dict]) -> list[dict]:
        """Filter pairs to only include USD/stablecoin quote tokens."""
        usd_pairs = [
            p for p in pairs
            if p.get("quoteToken", {}).get("symbol", "").upper() in USD_QUOTE_SYMBOLS
        ]
        return usd_pairs if usd_pairs else pairs  # fallback to all if no USD pairs

    @staticmethod
    def _sort_by_liquidity(pairs: list[dict]) -> list[dict]:
        """Sort pairs by liquidity (largest pools first)."""
        return sorted(
            pairs,
            key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
            reverse=True,
        )

    async def get_token_data(self, coin: dict) -> list[dict]:
        """Get best available DEX data for a coin config.

        Uses exact chain_id + token_address when available.
        Filters to USD/USDC pairs and sorts by largest liquidity.
        """
        pairs = []

        # Primary: use chain_id + token_address (exact match)
        if coin.get("chain_id") and coin.get("token_address"):
            pairs = await self.get_token_pairs(coin["chain_id"], coin["token_address"])

        # Fallback: search by query
        if not pairs:
            query = coin.get("dex_search_query") or coin.get("symbol", "")
            pairs = await self.search_pairs(query)
            # Filter to correct token
            symbol = coin.get("symbol", "").upper()
            pairs = [
                p for p in pairs
                if p.get("baseToken", {}).get("symbol", "").upper() == symbol
            ] or pairs[:5]

        # Filter to USD/USDC pairs and sort by largest liquidity
        pairs = self._filter_usd_pairs(pairs)
        pairs = self._sort_by_liquidity(pairs)

        return pairs

    def format_pair_data(self, pairs: list[dict]) -> str:
        """Format DEX pair data into readable text for AI analysis."""
        if not pairs:
            return "No DexScreener data available"

        lines = ["Source: DexScreener (Base chain, USD/USDC pools, sorted by liquidity)\n"]

        for i, pair in enumerate(pairs[:3]):  # Top 3 largest pools
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
            market_cap = pair.get("marketCap", 0)
            fdv = pair.get("fdv", 0)
            labels = pair.get("labels", [])

            h24_buys = txns.get("h24", {}).get("buys", 0)
            h24_sells = txns.get("h24", {}).get("sells", 0)
            h6_buys = txns.get("h6", {}).get("buys", 0)
            h6_sells = txns.get("h6", {}).get("sells", 0)
            h1_buys = txns.get("h1", {}).get("buys", 0)
            h1_sells = txns.get("h1", {}).get("sells", 0)
            m5_buys = txns.get("m5", {}).get("buys", 0)
            m5_sells = txns.get("m5", {}).get("sells", 0)

            # Calculate buy/sell ratio
            total_24h = h24_buys + h24_sells
            buy_pct = (h24_buys / total_24h * 100) if total_24h > 0 else 0

            version = f" ({', '.join(labels)})" if labels else ""
            lines.append(
                f"--- Pool #{i+1}: {base.get('symbol','?')}/{quote_token.get('symbol','?')} "
                f"on {dex}{version} ({chain}) ---"
            )
            lines.append(f"Price USD: ${price_usd}")
            lines.append(f"Market Cap: ${market_cap:,.0f}" if market_cap else "Market Cap: N/A")
            lines.append(f"FDV: ${fdv:,.0f}" if fdv else "FDV: N/A")
            lines.append(f"Price change 5m: {price_change.get('m5', 'N/A')}%")
            lines.append(f"Price change 1h: {price_change.get('h1', 'N/A')}%")
            lines.append(f"Price change 6h: {price_change.get('h6', 'N/A')}%")
            lines.append(f"Price change 24h: {price_change.get('h24', 'N/A')}%")
            lines.append(f"Volume 24h: ${volume.get('h24', 0):,.2f}")
            lines.append(f"Volume 6h: ${volume.get('h6', 0):,.2f}")
            lines.append(f"Volume 1h: ${volume.get('h1', 0):,.2f}")
            lines.append(f"Volume 5m: ${volume.get('m5', 0):,.2f}")
            lines.append(f"Liquidity USD: ${liquidity.get('usd', 0):,.2f}")
            lines.append(f"Txns 24h: {h24_buys} buys / {h24_sells} sells (buy ratio: {buy_pct:.1f}%)")
            lines.append(f"Txns 6h: {h6_buys} buys / {h6_sells} sells")
            lines.append(f"Txns 1h: {h1_buys} buys / {h1_sells} sells")
            lines.append(f"Txns 5m: {m5_buys} buys / {m5_sells} sells")
            if pair_url:
                lines.append(f"DexScreener URL: {pair_url}")
            lines.append("")

        return "\n".join(lines)
