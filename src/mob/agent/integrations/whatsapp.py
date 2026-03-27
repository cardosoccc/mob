"""WhatsApp integration tools for pydantic-ai agents."""

import logging
import os

import httpx
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0"


def register_whatsapp_tools(agent: Agent) -> None:
    """Register WhatsApp messaging tools with the agent."""

    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
    access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")

    @agent.tool_plain
    async def send_whatsapp_message(phone_number: str, message: str) -> str:
        """Send a WhatsApp message to a phone number.

        Args:
            phone_number: Recipient phone number in international format (e.g., +1234567890).
            message: The text message to send.
        """
        if not phone_number_id or not access_token:
            return "Error: WhatsApp credentials not configured"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{WHATSAPP_API_URL}/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": phone_number.lstrip("+"),
                    "type": "text",
                    "text": {"body": message},
                },
            )
            if resp.status_code == 200:
                return f"Message sent to {phone_number}"
            return f"Failed to send: {resp.status_code} {resp.text}"
