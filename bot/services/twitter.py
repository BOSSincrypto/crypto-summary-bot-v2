import httpx
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"


class TwitterService:
    """Twitter/X news scraper using Apify actors."""

    def __init__(self, apify_api_key: str = ""):
        self.apify_api_key = apify_api_key
        # Use a well-known free/cheap Twitter search actor
        self.actor_id = "quacker/twitter-scraper"

    async def search_tweets(self, queries: list[str], max_tweets: int = 20) -> list[dict]:
        """Search Twitter for mentions using Apify Twitter Scraper."""
        if not self.apify_api_key:
            logger.info("Apify API key not configured, skipping Twitter search")
            return []

        all_tweets = []
        for query in queries[:5]:  # Limit queries to save API calls
            tweets = await self._run_search(query, max_tweets=max_tweets // len(queries) + 1)
            all_tweets.extend(tweets)

        # Deduplicate by tweet ID
        seen_ids = set()
        unique = []
        for tweet in all_tweets:
            tid = tweet.get("id") or tweet.get("id_str") or tweet.get("url", "")
            if tid not in seen_ids:
                seen_ids.add(tid)
                unique.append(tweet)

        return unique[:max_tweets]

    async def _run_search(self, query: str, max_tweets: int = 10) -> list[dict]:
        """Run an Apify actor to search tweets."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                # Start the actor run
                run_input = {
                    "searchTerms": [query],
                    "maxTweets": max_tweets,
                    "sort": "Latest",
                    "tweetLanguage": "en",
                }

                # Try the synchronous run endpoint (waits for completion)
                resp = await client.post(
                    f"{APIFY_BASE}/acts/{self.actor_id}/run-sync-get-dataset-items",
                    params={"token": self.apify_api_key},
                    json=run_input,
                    timeout=120,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    return []
                else:
                    logger.warning(
                        f"Apify actor run failed (status {resp.status_code}): {resp.text[:200]}"
                    )
                    # Try alternative actor
                    return await self._run_alternative_search(client, query, max_tweets)

        except Exception as e:
            logger.error(f"Twitter search failed for '{query}': {e}")
            return []

    async def _run_alternative_search(self, client: httpx.AsyncClient,
                                       query: str, max_tweets: int) -> list[dict]:
        """Try alternative Apify actors for Twitter search."""
        alt_actors = [
            "apidojo/twitter-scraper-lite",
            "microworlds/twitter-scraper",
        ]
        for actor in alt_actors:
            try:
                run_input = {
                    "searchTerms": [query],
                    "maxItems": max_tweets,
                    "sort": "Latest",
                }
                resp = await client.post(
                    f"{APIFY_BASE}/acts/{actor}/run-sync-get-dataset-items",
                    params={"token": self.apify_api_key},
                    json=run_input,
                    timeout=120,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        return data
            except Exception as e:
                logger.debug(f"Alt actor {actor} failed: {e}")
                continue
        return []

    def format_tweets(self, tweets: list[dict]) -> str:
        """Format tweet data into readable text for AI analysis."""
        if not tweets:
            return "No Twitter/social media data available (Apify API key may not be configured)"

        lines = ["Source: Twitter/X (via Apify)\n"]
        for i, tweet in enumerate(tweets[:15]):
            # Handle different tweet data formats from various Apify actors
            text = (
                tweet.get("full_text")
                or tweet.get("text")
                or tweet.get("tweet_text")
                or tweet.get("content")
                or "N/A"
            )
            author = (
                tweet.get("user", {}).get("screen_name")
                or tweet.get("author", {}).get("userName")
                or tweet.get("username")
                or tweet.get("screen_name")
                or "Unknown"
            )
            likes = (
                tweet.get("favorite_count")
                or tweet.get("likeCount")
                or tweet.get("likes")
                or 0
            )
            retweets = (
                tweet.get("retweet_count")
                or tweet.get("retweetCount")
                or tweet.get("retweets")
                or 0
            )
            created = (
                tweet.get("created_at")
                or tweet.get("createdAt")
                or tweet.get("date")
                or "N/A"
            )

            # Truncate long tweets
            if len(text) > 200:
                text = text[:200] + "..."

            lines.append(f"Tweet #{i+1} by @{author} ({created}):")
            lines.append(f"  {text}")
            lines.append(f"  Likes: {likes} | Retweets: {retweets}")
            lines.append("")

        return "\n".join(lines)
