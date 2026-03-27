"""Integration registry - loads and registers platform tools based on configuration."""

import logging
import os

from pydantic_ai import Agent

logger = logging.getLogger(__name__)


def register_integrations(agent: Agent) -> None:
    """Register enabled integration tools with the pydantic-ai agent.

    Reads AGENT_CUSTOM_*_ENABLED env vars to determine which integrations to load.
    """
    if os.environ.get("AGENT_CUSTOM_WHATSAPP_ENABLED", "").lower() == "true":
        try:
            from mob.agent.integrations.whatsapp import register_whatsapp_tools
            register_whatsapp_tools(agent)
            logger.info("WhatsApp integration enabled")
        except Exception:
            logger.exception("Failed to register WhatsApp integration")

    if os.environ.get("AGENT_CUSTOM_TELEGRAM_ENABLED", "").lower() == "true":
        try:
            from mob.agent.integrations.telegram import register_telegram_tools
            register_telegram_tools(agent)
            logger.info("Telegram integration enabled")
        except Exception:
            logger.exception("Failed to register Telegram integration")

    if os.environ.get("AGENT_CUSTOM_LINKEDIN_ENABLED", "").lower() == "true":
        try:
            from mob.agent.integrations.linkedin import register_linkedin_tools
            register_linkedin_tools(agent)
            logger.info("LinkedIn integration enabled")
        except Exception:
            logger.exception("Failed to register LinkedIn integration")

    if os.environ.get("AGENT_CUSTOM_INSTAGRAM_ENABLED", "").lower() == "true":
        try:
            from mob.agent.integrations.instagram import register_instagram_tools
            register_instagram_tools(agent)
            logger.info("Instagram integration enabled")
        except Exception:
            logger.exception("Failed to register Instagram integration")
