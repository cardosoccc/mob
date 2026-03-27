"""Telegram integration tools for pydantic-ai agents."""

import logging
import os

import httpx
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org"


def register_telegram_tools(agent: Agent) -> None:
    """Register Telegram messaging tools with the agent."""

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @agent.tool_plain
    async def send_telegram_message(chat_id: str, message: str) -> str:
        """Send a Telegram message to a chat.

        Args:
            chat_id: The Telegram chat ID to send the message to.
            message: The text message to send.
        """
        if not bot_token:
            return "Error: Telegram bot token not configured"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{TELEGRAM_API_URL}/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": message},
            )
            if resp.status_code == 200:
                return f"Message sent to chat {chat_id}"
            return f"Failed to send: {resp.status_code} {resp.text}"

    @agent.tool_plain
    async def get_telegram_updates() -> str:
        """Get recent messages from the Telegram bot.

        Returns a summary of recent messages received by the bot.
        """
        if not bot_token:
            return "Error: Telegram bot token not configured"

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{TELEGRAM_API_URL}/bot{bot_token}/getUpdates",
                params={"limit": 10},
            )
            if resp.status_code != 200:
                return f"Failed to get updates: {resp.status_code}"

            updates = resp.json().get("result", [])
            if not updates:
                return "No recent messages"

            lines = []
            for update in updates:
                msg = update.get("message", {})
                text = msg.get("text", "")
                from_user = msg.get("from", {}).get("first_name", "Unknown")
                chat_id = msg.get("chat", {}).get("id", "")
                lines.append(f"From {from_user} (chat {chat_id}): {text}")
            return "\n".join(lines)
