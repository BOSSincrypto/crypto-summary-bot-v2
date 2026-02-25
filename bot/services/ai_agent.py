import httpx
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"


class AIAgent:
    """AI agent powered by OpenRouter for crypto analysis.

    Supports trainable templates and persistent memory.
    """

    def __init__(self, api_key: str, model: str = "google/gemma-3n-e4b-it"):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/BOSSincrypto/crypto-summary-bot-v2",
            "X-Title": "Crypto Summary Bot",
        }

    async def generate_summary(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a summary using the AI model."""
        if not self.api_key:
            return "AI agent not configured (missing OpenRouter API key)"

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }

                resp = await client.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "No response generated")
                    return "AI returned empty response"
                else:
                    error_msg = resp.text[:300]
                    logger.error(f"OpenRouter API error ({resp.status_code}): {error_msg}")
                    return f"AI analysis unavailable (API error {resp.status_code})"

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return f"AI analysis unavailable: {str(e)[:100]}"

    async def analyze_with_context(
        self,
        db,
        coin_symbol: str,
        coin_name: str,
        report_type: str,
        market_data: str,
        dex_data: str,
        twitter_data: str,
    ) -> str:
        """Generate a full analysis using templates and memory from the database."""
        # Load system prompt template
        system_prompt = await db.get_template("system_prompt")
        if not system_prompt:
            system_prompt = "You are a cryptocurrency analyst. Provide clear market summaries."

        # Load summary template
        summary_template = await db.get_template("summary_template")
        if not summary_template:
            summary_template = (
                "Generate a {report_type} summary for {coin_name} ({coin_symbol}).\n\n"
                "Market Data:\n{market_data}\n\nDEX Data:\n{dex_data}\n\n"
                "Social Media:\n{twitter_data}\n\nAI Memory:\n{ai_memory}"
            )

        # Load AI memory
        memory_entries = await db.get_all_memory()
        ai_memory = "\n".join(
            f"- {m['key']}: {m['value']}" for m in memory_entries
        ) if memory_entries else "No learned context yet"

        # Format the user prompt
        user_prompt = summary_template.format(
            report_type=report_type,
            coin_name=coin_name,
            coin_symbol=coin_symbol,
            market_data=market_data,
            dex_data=dex_data,
            twitter_data=twitter_data,
            ai_memory=ai_memory,
        )

        return await self.generate_summary(system_prompt, user_prompt)

    async def learn(self, db, key: str, value: str) -> str:
        """Store a new piece of learned knowledge in AI memory."""
        await db.set_memory(key, value)
        return f"Learned: {key} = {value}"

    async def ask_question(self, question: str) -> str:
        """Answer a general question about crypto or the bot."""
        system = (
            "You are a helpful cryptocurrency assistant. "
            "Answer questions clearly and concisely. "
            "If you don't know something, say so honestly."
        )
        return await self.generate_summary(system, question, temperature=0.5, max_tokens=1000)
