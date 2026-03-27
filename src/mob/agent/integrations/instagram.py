"""Instagram integration tools for pydantic-ai agents."""

import asyncio
import logging
import os

import httpx
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

INSTAGRAM_API_URL = "https://graph.facebook.com/v21.0"


def register_instagram_tools(agent: Agent) -> None:
    """Register Instagram posting tools with the agent."""

    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    business_account_id = os.environ.get("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

    @agent.tool_plain
    async def post_to_instagram(image_url: str, caption: str) -> str:
        """Publish a photo post on Instagram.

        Args:
            image_url: A publicly accessible URL of the image to post.
            caption: The caption text for the post.
        """
        if not access_token or not business_account_id:
            return "Error: Instagram credentials not configured (need INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID)"

        async with httpx.AsyncClient() as client:
            # Step 1: Create a media container
            resp = await client.post(
                f"{INSTAGRAM_API_URL}/{business_account_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": access_token,
                },
            )
            if resp.status_code != 200:
                return f"Failed to create media container: {resp.status_code} {resp.text}"

            container_id = resp.json().get("id")
            if not container_id:
                return "Failed to create media container: no ID returned"

            # Step 2: Poll for container readiness (max 30 seconds)
            for _ in range(6):
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{INSTAGRAM_API_URL}/{container_id}",
                    params={
                        "fields": "status_code",
                        "access_token": access_token,
                    },
                )
                if status_resp.status_code == 200:
                    status = status_resp.json().get("status_code")
                    if status == "FINISHED":
                        break
                    if status == "ERROR":
                        return "Media container processing failed"

            # Step 3: Publish the container
            publish_resp = await client.post(
                f"{INSTAGRAM_API_URL}/{business_account_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
            )
            if publish_resp.status_code == 200:
                post_id = publish_resp.json().get("id", "unknown")
                return f"Instagram post published (ID: {post_id})"
            return f"Failed to publish: {publish_resp.status_code} {publish_resp.text}"
