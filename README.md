# AI Image & Voice Bot

A Telegram bot that creates AI images and text-to-speech voiceover videos.

## Features

- `/image prompt` — generate an image with the free, community-powered AI Horde API.
- `/voice text` — turn Amharic text into an MP4 voiceover using Microsoft Azure Amharic voice through JSON2Video.
- `/voice_en text` — generate an English voiceover video.
- Inline menu buttons, prompt entry, queue polling, clear error messages and a Railway `/health` endpoint.
- No API key is required for basic AI Horde access. Anonymous requests use the public key and have the lowest queue priority.
- JSON2Video requires a free API key. New accounts receive 600 non-renewable credits; free renders are limited to 60 seconds and may include a watermark.

## Required environment variables

- `BOT_TOKEN` — Telegram bot token from BotFather.
- `JSON2VIDEO_API_KEY` — API key from https://json2video.com/dashboard/apikeys (required for voice generation).
- `AI_HORDE_API_KEY` — optional registered AI Horde key; defaults to the anonymous key `0000000000`.
- `LOG_LEVEL` — optional, defaults to `INFO`.

Never commit API keys or paste them into public chats. Add them in Railway → Service → Variables.

## Commands

- `/start` — open the AI Image & Voice menu.
- `/image a cinematic mountain landscape` — generate an image.
- `/voice ሰላም እንዴት ነህ?` — Amharic voiceover (Mekdes).
- `/voice_en Hello there` — English voiceover.
- `/help` — usage and provider details.

## Free-tier notes

AI Horde is a volunteer-run service, so anonymous requests may wait in a queue. A free registered key improves priority.

JSON2Video's free plan currently includes 600 one-time credits, with a 60-second maximum per render. The bot returns an MP4 containing the synthesized voice. Downloading a standalone MP3 audio track is a paid-plan feature; free renders may carry a watermark. The app does not purchase credits or upgrade plans automatically.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set BOT_TOKEN and JSON2VIDEO_API_KEY in .env
python -m bot.main
```

## Safety

The bot is for lawful narration of text the user is authorized to use. It does not offer voice cloning, celebrity imitation, impersonation or deceptive audio generation.
