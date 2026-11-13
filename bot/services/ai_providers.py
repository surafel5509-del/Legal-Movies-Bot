from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

import aiohttp


class ProviderError(RuntimeError):
    pass


class AIProviders:
    """Thin async clients for AI Horde image generation and JSON2Video Azure TTS."""

    HORDE_API = "https://aihorde.net/api/v2"
    JSON2VIDEO_API = "https://api.json2video.com/v2"

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.json2video_key = os.getenv("JSON2VIDEO_API_KEY", "").strip()
        self.horde_key = os.getenv("AI_HORDE_API_KEY", "0000000000").strip() or "0000000000"

    async def generate_image(self, prompt: str) -> bytes:
        headers = {
            "apikey": self.horde_key,
            "Client-Agent": "Surafel-AI-Image-Voice-Bot:1.0",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": prompt,
            "params": {
                "width": 768,
                "height": 768,
                "steps": 25,
                "n": 1,
                "cfg_scale": 7.0,
                "sampler_name": "k_euler",
            },
            "nsfw": False,
            "censor_nsfw": True,
        }
        async with self.session.post(
            f"{self.HORDE_API}/generate/async",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=45),
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise ProviderError(data.get("message", "AI Horde rejected the image request."))
            request_id = data.get("id")
            if not request_id:
                raise ProviderError("AI Horde did not return a generation ID.")

        # Community workers are volunteer-run; anonymous requests can wait in a queue.
        for _ in range(90):
            await asyncio.sleep(5)
            async with self.session.get(
                f"{self.HORDE_API}/generate/status/{request_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                status: dict[str, Any] = await response.json(content_type=None)
                if response.status >= 400:
                    raise ProviderError(status.get("message", "Could not read AI Horde job status."))
            if status.get("faulted"):
                raise ProviderError("AI Horde could not complete this image. Please try another prompt.")
            generations = status.get("generations") or []
            if status.get("done") and generations:
                encoded = generations[0].get("img")
                if not encoded:
                    raise ProviderError("AI Horde completed the job but returned no image.")
                try:
                    return base64.b64decode(encoded, validate=True)
                except (ValueError, TypeError) as exc:
                    raise ProviderError("AI Horde returned an invalid image payload.") from exc
        raise ProviderError("Image generation is taking longer than expected. Please try again later.")

    async def generate_voice_video(self, text: str, voice: str = "am-ET-MekdesNeural") -> str:
        if not self.json2video_key:
            raise ProviderError(
                "JSON2VIDEO_API_KEY is not configured. Add your free JSON2Video API key "
                "to Railway Variables, then try again."
            )
        headers = {
            "x-api-key": self.json2video_key,
            "Content-Type": "application/json",
        }
        movie = {
            "resolution": "full-hd",
            "scenes": [
                {
                    "elements": [
                        {
                            "type": "text",
                            "text": "AI VOICE GENERATOR",
                            "style": "001",
                            "duration": 5,
                        },
                        {
                            "type": "voice",
                            "text": text,
                            "voice": voice,
                            "model": "azure",
                            "duration": -1,
                            "cache": True,
                        },
                    ]
                }
            ],
        }
        async with self.session.post(
            f"{self.JSON2VIDEO_API}/movies",
            headers=headers,
            json=movie,
            timeout=aiohttp.ClientTimeout(total=45),
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400 or not data.get("project"):
                raise ProviderError(data.get("message", "JSON2Video could not start the voice render."))
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
                    raise ProviderError(data.get("message", "Could not read voice render status."))
            result = data.get("movie") or {}
            state = result.get("status")
            if state == "done" and result.get("url"):
                return result["url"]
            if state in {"error", "timeout"}:
                raise ProviderError(result.get("message") or "JSON2Video could not render this voiceover.")
        raise ProviderError("Voice generation is taking longer than expected. Please try again later.")
