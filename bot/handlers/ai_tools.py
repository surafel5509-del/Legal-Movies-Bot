from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from bot.services.ai_providers import AIProviders, ProviderError

router = Router(name="ai-studio")
log = logging.getLogger(__name__)

IMAGE_DEFAULTS = {"width": 512, "height": 512, "steps": 12, "style": "cinematic"}
VOICE_DEFAULT = "am-ET-MekdesNeural"
VOICE_CHOICES = {
    "am": ("🇪🇹 አማርኛ · መቅደስ", "am-ET-MekdesNeural"),
    "en_f": ("🇺🇸 English · Emma", "en-US-EmmaMultilingualNeural"),
    "en_m": ("🇺🇸 English · Andrew", "en-US-AndrewMultilingualNeural"),
}
IMAGE_STYLES = {
    "cinematic": "cinematic lighting, professional composition, highly detailed",
    "realistic": "photorealistic, natural lighting, realistic textures",
    "anime": "high quality anime illustration, expressive details",
    "digital_art": "polished digital concept art, rich colors, intricate details",
}
STYLE_LABELS = {
    "cinematic": "🎬 Cinematic",
    "realistic": "📷 Realistic",
    "anime": "🌸 Anime",
    "digital_art": "🖌 Digital Art",
}


class GenerationStates(StatesGroup):
    image_prompt = State()
    voice_text = State()
    english_voice_text = State()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎨 Create Image"), KeyboardButton(text="🔊 Text to Voice")],
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="ℹ️ Help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Choose an AI Studio tool…",
    )


def home_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Generate Image", callback_data="studio:image"),
         InlineKeyboardButton(text="🔊 Generate Voice", callback_data="studio:voice")],
        [InlineKeyboardButton(text="⚙️ Personalize Settings", callback_data="studio:settings")],
        [InlineKeyboardButton(text="📖 How to use", callback_data="studio:help")],
    ])


def settings_keyboard(data: dict) -> InlineKeyboardMarkup:
    width = int(data.get("image_width", IMAGE_DEFAULTS["width"]))
    steps = int(data.get("image_steps", IMAGE_DEFAULTS["steps"]))
    style = data.get("image_style", IMAGE_DEFAULTS["style"])
    voice_key = data.get("voice_key", "am")
    size_label = f"{width}×{width}"
    quality_label = {8: "Draft", 12: "Standard", 16: "High"}.get(steps, "Standard")
    voice_label = VOICE_CHOICES.get(voice_key, VOICE_CHOICES["am"])[0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🖼 Size: {size_label}", callback_data="settings:size")],
        [InlineKeyboardButton(text=f"✨ Quality: {quality_label}", callback_data="settings:quality")],
        [InlineKeyboardButton(text=f"🎨 Style: {STYLE_LABELS.get(style, STYLE_LABELS['cinematic'])}", callback_data="settings:style")],
        [InlineKeyboardButton(text=f"🗣 Voice: {voice_label}", callback_data="settings:voice")],
        [InlineKeyboardButton(text="↩️ Main Menu", callback_data="studio:home")],
    ])


def choice_keyboard(kind: str, current: str) -> InlineKeyboardMarkup:
    if kind == "size":
        options = [("384×384 · Fast", "384"), ("512×512 · Balanced", "512"), ("576×576 · Detailed", "576")]
        prefix = "size"
    elif kind == "quality":
        options = [("Draft · 8 steps", "8"), ("Standard · 12 steps", "12"), ("High · 16 steps", "16")]
        prefix = "quality"
    elif kind == "style":
        options = [(STYLE_LABELS[k], k) for k in IMAGE_STYLES]
        prefix = "style"
    else:
        options = [(v[0], k) for k, v in VOICE_CHOICES.items()]
        prefix = "voice"
    rows = [[InlineKeyboardButton(text=("✓ " if value == current else "") + label, callback_data=f"set:{prefix}:{value}")]
            for label, value in options]
    rows.append([InlineKeyboardButton(text="↩️ Back to Settings", callback_data="studio:settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_home(message: Message, state: FSMContext | None = None) -> None:
    if state:
        await state.set_state(None)
    await message.answer(
        "✨ <b>Welcome to AI Studio</b>\n"
        "<i>Your creative workspace for AI images and natural voiceovers.</i>\n\n"
        "🎨 <b>Image Studio</b>  · Create artwork from a text prompt\n"
        "🔊 <b>Voice Studio</b>  · Turn Amharic or English text into speech\n"
        "⚙️ <b>Settings</b>  · Choose image quality, style, and voice",
        reply_markup=main_keyboard(),
    )
    await message.answer("Choose a tool to get started:", reply_markup=home_inline())


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await show_home(message, state)


@router.message(Command("menu"))
@router.message(F.text == "🏠 Main Menu")
async def menu_command(message: Message, state: FSMContext) -> None:
    await show_home(message, state)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.set_state(None)
    await message.answer("Cancelled. Your settings have been kept.", reply_markup=main_keyboard())


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Help")
async def help_command(message: Message) -> None:
    await message.answer(
        "<b>AI Studio · Quick Guide</b>\n\n"
        "🎨 <code>/image your prompt</code> — generate an image\n"
        "🔊 <code>/voice your Amharic text</code> — Amharic voiceover\n"
        "🇺🇸 <code>/voice_en your English text</code> — English voiceover\n"
        "⚙️ <code>/settings</code> — image and voice preferences\n"
        "🏠 <code>/menu</code> — return to the main menu\n"
        "✖️ <code>/cancel</code> — cancel the current input\n\n"
        "Free AI Horde generation uses community volunteers. Small images are prioritized; queue times vary with demand. "
        "Voice output is delivered as MP4 by the configured JSON2Video plan.",
        reply_markup=home_inline(),
    )


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Settings")
async def settings_command(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer("<b>⚙️ Your Studio Settings</b>\nChoose how your next creation should look or sound.", reply_markup=settings_keyboard(data))


@router.callback_query(F.data == "studio:home")
async def home_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await show_home(callback.message, state)


@router.callback_query(F.data == "studio:settings")
async def settings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.message.edit_text("<b>⚙️ Your Studio Settings</b>\nThese preferences are used for your next generation.", reply_markup=settings_keyboard(data))
    await callback.answer()


@router.callback_query(F.data.startswith("settings:"))
async def setting_picker(callback: CallbackQuery, state: FSMContext) -> None:
    kind = callback.data.split(":", 1)[1]
    data = await state.get_data()
    current = {
        "size": str(data.get("image_width", 512)),
        "quality": str(data.get("image_steps", 12)),
        "style": data.get("image_style", "cinematic"),
        "voice": data.get("voice_key", "am"),
    }.get(kind, "")
    await callback.message.edit_text(f"<b>Choose {kind.title()}</b>", reply_markup=choice_keyboard(kind, current))
    await callback.answer()


@router.callback_query(F.data.startswith("set:"))
async def save_setting(callback: CallbackQuery, state: FSMContext) -> None:
    _, kind, value = callback.data.split(":", 2)
    keys = {"size": "image_width", "quality": "image_steps", "style": "image_style", "voice": "voice_key"}
    valid = {
        "size": {"384", "512", "576"},
        "quality": {"8", "12", "16"},
        "style": set(IMAGE_STYLES),
        "voice": set(VOICE_CHOICES),
    }
    if kind not in keys or value not in valid[kind]:
        await callback.answer("Invalid setting.", show_alert=True)
        return
    stored: str | int = int(value) if kind in {"size", "quality"} else value
    await state.update_data({keys[kind]: stored})
    data = await state.get_data()
    await callback.message.edit_text("✅ <b>Settings saved</b>\nYour preferences will be used for the next generation.", reply_markup=settings_keyboard(data))
    await callback.answer("Saved")


@router.callback_query(F.data == "studio:image")
async def image_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GenerationStates.image_prompt)
    await callback.message.answer("🎨 <b>Image Studio</b>\nDescribe the image you want to create.\n\n<i>Tip: include subject, setting, lighting, mood, and art style.</i>\nSend /cancel to stop.")
    await callback.answer()


@router.callback_query(F.data == "studio:voice")
async def voice_button(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    voice_key = data.get("voice_key", "am")
    label = VOICE_CHOICES.get(voice_key, VOICE_CHOICES["am"])[0]
    await state.set_state(GenerationStates.voice_text)
    await callback.message.answer(f"🔊 <b>Voice Studio</b>\nSelected voice: {label}\nSend the text you want spoken (up to 600 characters).\nSend /cancel to stop.")
    await callback.answer()


@router.callback_query(F.data == "studio:help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    await help_command(callback.message)


@router.message(Command("image"))
async def image_command(message: Message, state: FSMContext, ai: AIProviders) -> None:
    prompt = (message.text or "").partition(" ")[2].strip()
    if not prompt:
        await state.set_state(GenerationStates.image_prompt)
        await message.answer("🎨 Send the prompt for your image. Use /cancel to stop.")
        return
    await make_image(message, prompt, ai, await state.get_data())


@router.message(GenerationStates.image_prompt, F.text)
async def image_prompt(message: Message, state: FSMContext, ai: AIProviders) -> None:
    prompt = (message.text or "").strip()
    await state.set_state(None)
    await make_image(message, prompt, ai, await state.get_data())


@router.message(F.text == "🎨 Create Image")
async def image_menu_text(message: Message, state: FSMContext) -> None:
    await state.set_state(GenerationStates.image_prompt)
    await message.answer("🎨 Describe the image you want to create. Use /cancel to stop.")


async def make_image(message: Message, prompt: str, ai: AIProviders, settings: dict) -> None:
    if not prompt or len(prompt) > 1200:
        await message.answer("Please send an image prompt between 1 and 1,200 characters.")
        return
    width = int(settings.get("image_width", 512))
    steps = int(settings.get("image_steps", 12))
    style = settings.get("image_style", "cinematic")
    enhanced_prompt = f"{prompt.strip()}, {IMAGE_STYLES.get(style, IMAGE_STYLES['cinematic'])}"
    status = await message.answer(f"🎨 <b>Creating your image…</b>\n🖼 {width}×{width} · {steps} steps\n⏳ Free community workers may take a few minutes.")
    try:
        image, note = await ai.generate_image(enhanced_prompt, width=width, height=width, steps=steps)
        await message.answer_photo(
            BufferedInputFile(image, filename="ai-studio-image.webp"),
            caption=f"✨ <b>Your creation is ready</b>\n{note}\nStyle: {STYLE_LABELS.get(style, 'Cinematic')}",
        )
        await status.delete()
    except ProviderError as exc:
        await status.edit_text(f"⚠️ <b>Image generation failed</b>\n{exc}\n\nTry 384×384 / Draft in ⚙️ Settings, or retry later.")
    except Exception:
        log.exception("Unexpected image generation error")
        await status.edit_text("⚠️ Something unexpected happened while creating your image. Please try again.")


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
    await state.set_state(None)
    data = await state.get_data()
    voice_key = data.get("voice_key", "am")
    voice_label, voice_id = VOICE_CHOICES.get(voice_key, VOICE_CHOICES["am"])
    language = "Amharic" if voice_key == "am" else "English"
    await make_voice(message, text, ai, voice_id, language)


@router.message(GenerationStates.english_voice_text, F.text)
async def english_voice_text(message: Message, state: FSMContext, ai: AIProviders) -> None:
    text = (message.text or "").strip()
    await state.set_state(None)
    await make_voice(message, text, ai, "en-US-EmmaMultilingualNeural", "English")


@router.message(F.text == "🔊 Text to Voice")
async def voice_menu_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    voice_key = data.get("voice_key", "am")
    await state.set_state(GenerationStates.voice_text)
    await message.answer("🔊 Send the text you want spoken. Change the preferred voice in ⚙️ Settings.")


async def make_voice(message: Message, text: str, ai: AIProviders, voice: str, language: str) -> None:
    if not text or len(text) > 600:
        await message.answer("Please send text between 1 and 600 characters. The free plan has a 60-second output limit.")
        return
    status = await message.answer(f"🔊 <b>Creating your {language} voiceover…</b>\nThis may take a minute or two.")
    try:
        url = await ai.generate_voice_video(text, voice=voice)
        await message.answer_video(
            video=url,
            caption=f"🎧 <b>{language} AI voiceover</b>\nGenerated with Microsoft Azure TTS via JSON2Video.",
            supports_streaming=True,
        )
        await status.delete()
    except ProviderError as exc:
        await status.edit_text(f"⚠️ <b>Voice generation failed</b>\n{exc}")
    except Exception:
        log.exception("Unexpected voice generation error")
        await status.edit_text("⚠️ Something went wrong while creating the voiceover. Please try again.")
