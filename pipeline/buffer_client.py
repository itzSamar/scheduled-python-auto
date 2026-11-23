"""
Publish a finished Short through Buffer to every connected channel.

Buffer has no file upload. The mp4 is hosted at a public HTTPS URL first, then
createPost is called once per channel with mode shareNow. YouTube gets a title
and category; TikTok gets the caption plus an AI-voice disclosure.
"""
import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests

from .config import BUFFER_API_KEY, BUFFER_API_URL

logger = logging.getLogger(__name__)

YOUTUBE_CATEGORY_ENTERTAINMENT = "24"


class BufferError(RuntimeError):
    pass


class BufferClient:
    def __init__(self, api_key: str = "", url: str = ""):
        self.api_key = api_key or BUFFER_API_KEY
        self.url = url or BUFFER_API_URL
        if not self.api_key:
            raise BufferError("BUFFER_API_KEY is missing. Add it to .env.local (Buffer → Settings → API).")

    def graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.post(
            self.url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables or {}},
            timeout=90,
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise BufferError(f"Buffer returned {response.status_code} with a non-JSON body") from exc
        if body.get("errors"):
            raise BufferError(body["errors"][0].get("message") or str(body["errors"]))
        if response.status_code >= 400 or "data" not in body:
            raise BufferError(f"Buffer request failed ({response.status_code})")
        return body["data"]

    def channels(self) -> List[Dict[str, Any]]:
        orgs = self.graphql("query { account { organizations { id name } } }")
        found: List[Dict[str, Any]] = []
        query = """
        query($id: OrganizationId!) {
          channels(input: { organizationId: $id }) {
            id name displayName service isQueuePaused
          }
        }
        """
        for org in orgs["account"]["organizations"]:
            data = self.graphql(query, {"id": org["id"]})
            for channel in data["channels"]:
                channel["organizationName"] = org["name"]
                found.append(channel)
        return found

    def create_video_post(
        self,
        channel: Dict[str, Any],
        *,
        text: str,
        video_url: str,
        title: str,
        thumbnail_ms: int = 8000,
        mode: str = "shareNow",
        due_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        service = (channel.get("service") or "").lower()
        video: Dict[str, Any] = {"url": video_url}
        metadata: Dict[str, Any] = {}
        if service == "youtube":
            metadata["youtube"] = {
                "title": title[:100],
                "categoryId": YOUTUBE_CATEGORY_ENTERTAINMENT,
                "privacy": "public",
                "madeForKids": False,
                "notifySubscribers": True,
                "embeddable": True,
                "isAiGenerated": True,
            }
        elif service == "tiktok":
            video["metadata"] = {"thumbnailOffset": thumbnail_ms}
            metadata["tiktok"] = {"isAiGenerated": True}
        else:
            raise BufferError(f"No post format for Buffer service {service!r}")

        data = self.graphql(
            """
            mutation($input: CreatePostInput!) {
              createPost(input: $input) {
                ... on PostActionSuccess {
                  post { id status dueAt sentAt externalLink shareMode }
                }
                ... on MutationError { message }
              }
            }
            """,
            {"input": {
                "text": text,
                "channelId": channel["id"],
            "schedulingType": "automatic",
            "mode": mode,
            **({"dueAt": due_at} if due_at else {}),
            "assets": [{"video": video}],
                "metadata": metadata,
                "aiAssisted": True,
            }},
        )
        result = data["createPost"]
        if not result.get("post"):
            raise BufferError(result.get("message") or f"{service} post was rejected")
        post = result["post"]
        post["service"] = service
        return post

    def post_status(self, post_id: str) -> Dict[str, Any]:
        data = self.graphql(
            """
            query($id: PostId!) {
              post(input: { id: $id }) {
                id status sentAt externalLink
                error { message rawError supportUrl }
              }
            }
            """,
            {"id": post_id},
        )
        return data["post"]

    def wait_until_settled(self, post_id: str, timeout: float = 180) -> Dict[str, Any]:
        deadline = time.time() + timeout
        last = {}
        while time.time() < deadline:
            last = self.post_status(post_id)
            if last.get("status") in ("sent", "error"):
                return last
            time.sleep(5)
        return last


def host_video(path: str) -> str:
    """Upload the mp4 to a public host Buffer can fetch. Returns a direct HTTPS URL."""
    name = os.path.basename(path)
    with open(path, "rb") as handle:
        response = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (name, handle, "video/mp4")},
            timeout=300,
        )
    url = (response.text or "").strip()
    if response.status_code != 200 or not url.startswith("https://"):
        raise BufferError(f"Could not host the video ({response.status_code}): {url[:180]}")
    # requests gets its connection reset by this host; curl confirms the file is public.
    check = subprocess.run(
        ["curl", "-fsS", "-m", "30", "-r", "0-15", "-o", os.devnull, "-w", "%{http_code}", url],
        capture_output=True, text=True, timeout=40,
    )
    if check.stdout.strip() not in ("200", "206"):
        raise BufferError(f"Hosted URL is not publicly readable ({check.stdout.strip() or check.stderr[-180:]}): {url}")
    logger.info(f"Hosted video for Buffer: {url}")
    return url
