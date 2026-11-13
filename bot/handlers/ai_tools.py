from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.services.ai_providers import AIProviders, ProviderError

router = Router(name="ai-tools")
log = logging.getLogger(__name__)


class GenerationStates(StatesGroup):
    image_prompt = State()
    voice_text = State()
    english_voice_text = State()


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎨 Generate Image", callback_data="ai:image"),
            InlineKeyboardButton(text="🔊 Text to Voice", callback_data="ai:voice"),
        ],
        [InlineKeyboardButton(text="🇬🇧 English Voice", callback_data="ai:voice_en")],
    ])


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "✨ <b>AI Image & Voice Studio</b>\n\n"
        "🎨 Send a prompt to create an AI image.\n"
        "🔊 Turn Amharic text into a spoken voiceover video.\n"
        "🇬🇧 English voice is also available.\n\n"
        "Commands:\n"
        "/image — generate an image\n"
        "/voice — Amharic text to voice\n"
        "/voice_en — English text to voice\n"
        "/help — help and provider information",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>How to use the bot</b>\n\n"
        "• <code>/image a cinematic mountain landscape</code>\n"
        "• <code>/voice ሰላም እንዴት ነህ?</code>\n"
        "• <code>/voice_en Hello, welcome to my channel.</code>\n\n"
        "Image generation uses the free community-powered AI Horde. "
        "Voiceovers use JSON2Video's free starter credits and Microsoft Azure voices. "
        "Free voiceovers are delivered as MP4 video; standalone MP3 export requires a paid JSON2Video plan.\n\n"
        "Please use only text you have the right to narrate. Voice cloning and impersonation are not supported.",
        reply_markup=main_keyboard(),
    )


@router.callback_query(F.data == "ai:image")
async def image_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenerationStates.image_prompt)
    await callback.message.answer("🎨 Send the prompt for your image.")
    await callback.answer()


@router.callback_query(F.data == "ai:voice")
async def voice_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenerationStates.voice_text)
    await callback.message.answer("🔊 ወደ ድምፅ መቀየር የምትፈልገውን አማርኛ ጽሑፍ ላክ። (እስከ 600 ቁምፊ)")
    await callback.answer()


@router.callback_query(F.data == "ai:voice_en")
async def english_voice_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenerationStates.english_voice_text)
    await callback.message.answer("Send the English text you want spoken (up to 600 characters).")
    await callback.answer()


@router.message(Command("image"))
async def image_command(message: Message, state: FSMContext, ai: AIProviders) -> None:
    prompt = (message.text or "").partition(" ")[2].strip()
    if not prompt:
        await state.set_state(GenerationStates.image_prompt)
        await message.answer("🎨 Send the prompt for your image.")
        return
    await make_image(message, prompt, ai)


@router.message(GenerationStates.image_prompt, F.text)
async def image_prompt(message: Message, state: FSMContext, ai: AIProviders) -> None:
    prompt = (message.text or "").strip()
    await state.clear()
    await make_image(message, prompt, ai)


async def make_image(message: Message, prompt: str, ai: AIProviders) -> None:
    if not prompt or len(prompt) > 1200:
        await message.answer("Please send an image prompt between 1 and 1,200 characters.")
        return
    status = await message.answer("🎨 <b>Image is being generated...</b>\nAI Horde workers may take a little time.")
    try:
        image = await ai.generate_image(prompt)
        await message.answer_photo(
            BufferedInputFile(image, filename="ai-horde-image.png"),
            caption="✨ Your AI-generated image",
        )
        await status.delete()
    except ProviderError as exc:
        await status.edit_text(f"⚠️ {exc}")
    except Exception:
        log.exception("Unexpected image generation error")
        await status.edit_text("⚠️ Something went wrong while generating the image. Please try again.")


@router.message(Command("voice"))
async def voice_command(message: Message, state: FSMContext, ai: AIProviders) -> None:
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await state.set_state(GenerationStates.voice_text)
        await message.answer("🔊 ወደ ድምፅ መቀየር የምትፈልገውን አማርኛ ጽሑፍ ላክ። (እስከ 600 ቁምፊ)")
        return
    await make_voice(message, text, ai, "am-ET-MekdesNeural", "Amharic")


@router.message(Command("voice_en"))
async def english_voice_command(message: Message, state: FSMContext, ai: AIProviders) -> None:
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await state.set_state(GenerationStates.english_voice_text)
        await message.answer("Send the English text you want spoken (up to 600 characters).")
        return
    await make_voice(message, text, ai, "en-US-EmmaMultilingualNeural", "English")


@router.message(GenerationStates.voice_text, F.text)
async def amharic_voice_text(message: Message, state: FSMContext, ai: AIProviders) -> None:
    text = (message.text or "").strip()
    await state.clear()
    await make_voice(message, text, ai, "am-ET-MekdesNeural", "Amharic")


@router.message(GenerationStates.english_voice_text, F.text)
async def english_voice_text(message: Message, state: FSMContext, ai: AIProviders) -> None:
    text = (message.text or "").strip()
    await state.clear()
    await make_voice(message, text, ai, "en-US-EmmaMultilingualNeural", "English")


async def make_voice(message: Message, text: str, ai: AIProviders, voice: str, language: str) -> None:
    if not text or len(text) > 600:
        await message.answer("Please send text between 1 and 600 characters. The free JSON2Video plan has a 60-second output limit.")
        return
    status = await message.answer(f"🔊 <b>Creating {language} voiceover...</b>\nThis may take a minute or two.")
    try:
        url = await ai.generate_voice_video(text, voice=voice)
        await message.answer_video(
            video=url,
            caption=f"🎧 {language} AI voiceover\nGenerated with Microsoft Azure TTS via JSON2Video.",
            supports_streaming=True,
        )
        await status.delete()
    except ProviderError as exc:
        await status.edit_text(f"⚠️ {exc}")
    except Exception:
        log.exception("Unexpected voice generation error")
        await status.edit_text("⚠️ Something went wrong while creating the voiceover. Please try again.")
