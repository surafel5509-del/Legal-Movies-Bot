from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import aiohttp


class ProviderError(RuntimeError):
    """A safe, user-displayable provider error."""


class AIProviders:
    """Async clients for AI Horde image generation and JSON2Video Azure TTS."""

    HORDE_API = "https://aihorde.net/api/v2"
    JSON2VIDEO_API = "https://api.json2video.com/v2"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.json2video_key = os.getenv("JSON2VIDEO_API_KEY", "").strip()
        self.horde_key = os.getenv("AI_HORDE_API_KEY", "0000000000").strip() or "0000000000"

    async def _submit_horde(self, prompt: str, width: int, height: int, steps: int) -> str:
        headers = {
            "apikey": self.horde_key,
            "Client-Agent": "Surafel-AI-Image-Voice-Studio:2.0",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "params": {
                "width": width,
                "height": height,
                "steps": steps,
                "n": 1,
                "cfg_scale": 7.0,
                "sampler_name": "k_euler",
                "karras": True,
            },
            "nsfw": False,
            "censor_nsfw": True,
            "r2": False,
            "allow_downgrade": True,
        }
        async with self.session.post(
            f"{self.HORDE_API}/generate/async",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=45),
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                message = str(data.get("message") or data.get("error") or "AI Horde rejected this request.")
                if "kudos" in message.lower() or "576x576" in message.lower():
                    raise ProviderError("AI Horde is busy and requires credits for larger jobs. The bot will retry with a smaller free-tier image. If this still fails, try again later or add a registered AI Horde key.")
                raise ProviderError(message[:450])
            request_id = data.get("id")
            if not request_id:
                raise ProviderError("AI Horde did not return a generation ID.")
            return str(request_id)

    async def _wait_for_horde(self, request_id: str) -> bytes:
        headers = {
            "apikey": self.horde_key,
            "Client-Agent": "Surafel-AI-Image-Voice-Studio:2.0",
        }
        # /check is intentionally polled; /status is fetched once after completion.
        for _ in range(120):
            await asyncio.sleep(5)
            async with self.session.get(
                f"{self.HORDE_API}/generate/check/{request_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                progress: dict[str, Any] = await response.json(content_type=None)
                if response.status >= 400:
                    raise ProviderError(str(progress.get("message") or "Could not read AI Horde job status.")[:450])
            if progress.get("faulted"):
                raise ProviderError("AI Horde workers could not complete this image. Please try a simpler prompt.")
            if progress.get("done"):
                async with self.session.get(
                    f"{self.HORDE_API}/generate/status/{request_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    result: dict[str, Any] = await response.json(content_type=None)
                    if response.status >= 400:
                        raise ProviderError(str(result.get("message") or "Could not retrieve the generated image.")[:450])
                generations = result.get("generations") or []
                if not generations or not generations[0].get("img"):
                    raise ProviderError("AI Horde completed the job but returned no image.")
                try:
                    raw = base64.b64decode(generations[0]["img"], validate=True)
                except (ValueError, TypeError) as exc:
                    raise ProviderError("AI Horde returned an invalid image payload.") from exc
                if not raw:
                    raise ProviderError("AI Horde returned an empty image.")
                return raw
        raise ProviderError("Image generation is taking longer than expected. The free worker queue may be busy; please try again.")

    async def generate_image(
        self,
        prompt: str,
        *,
        width: int = 512,
        height: int = 512,
        steps: int = 12,
    ) -> tuple[bytes, str]:
        """Generate image with free-tier-safe defaults and one automatic low-cost fallback."""
        try:
            request_id = await self._submit_horde(prompt, width, height, steps)
        except ProviderError as exc:
            # Some anonymous/community workers impose a tighter work budget.
            # Retry once at 384px/8 steps instead of requiring user kudos.
            if "retry with a smaller free-tier image" not in str(exc):
                raise
            request_id = await self._submit_horde(prompt, 384, 384, 8)
            fallback_note = "Generated with free-tier fallback settings (384×384)."
        else:
            fallback_note = f"Generated at {width}×{height}."

        return await self._wait_for_horde(request_id), fallback_note

    async def generate_voice_video(self, text: str, voice: str = "am-ET-MekdesNeural") -> str:
        if not self.json2video_key:
            raise ProviderError("Voice generation is not configured. Add JSON2VIDEO_API_KEY in Railway Variables.")
        headers = {"x-api-key": self.json2video_key, "Content-Type": "application/json"}
        movie = {
            "resolution": "full-hd",
            "scenes": [{
                "elements": [{
                    "type": "voice",
                    "text": text,
                    "voice": voice,
                    "model": "azure",
                    "duration": -1,
                    "cache": True,
                }]
            }],
        }
        async with self.session.post(
            f"{self.JSON2VIDEO_API}/movies",
            headers=headers,
            json=movie,
            timeout=aiohttp.ClientTimeout(total=45),
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400 or not data.get("project"):
                raise ProviderError(str(data.get("message") or "JSON2Video could not start the voice render.")[:450])
            project_id = data["project"]

        for _ in range(60):
            await asyncio.sleep(5)
            async with self.session.get(
                f"{self.JSON2VIDEO_API}/movies",
                params={"project": project_id, "format": "simple"},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise ProviderError(str(data.get("message") or "Could not read voice render status.")[:450])
            result = data.get("movie") or {}
            state = result.get("status")
            if state == "done" and result.get("url"):
                return str(result["url"])
            if state in {"error", "timeout"}:
                raise ProviderError(str(result.get("message") or "JSON2Video could not render this voiceover.")[:450])
        raise ProviderError("Voice generation is taking longer than expected. Please try again.")
