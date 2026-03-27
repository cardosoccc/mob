"""LinkedIn integration tools for pydantic-ai agents."""

import logging
import os

import httpx
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

LINKEDIN_API_URL = "https://api.linkedin.com/v2"


def register_linkedin_tools(agent: Agent) -> None:
    """Register LinkedIn posting tools with the agent."""

    access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    person_urn = os.environ.get("LINKEDIN_PERSON_URN", "")

    @agent.tool_plain
    async def post_to_linkedin(text: str, image_url: str | None = None) -> str:
        """Publish a post on LinkedIn.

        Args:
            text: The post text content.
            image_url: Optional URL of an image to include in the post.
        """
        if not access_token or not person_urn:
            return "Error: LinkedIn credentials not configured (need LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN)"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # Build the post payload
        payload = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        # Add image if provided
        if image_url:
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
            payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
                {
                    "status": "READY",
                    "originalUrl": image_url,
                }
            ]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{LINKEDIN_API_URL}/ugcPosts",
                headers=headers,
                json=payload,
            )
            if resp.status_code in (200, 201):
                post_id = resp.headers.get("x-restli-id", "unknown")
                return f"LinkedIn post published (ID: {post_id})"
            return f"Failed to post: {resp.status_code} {resp.text}"
