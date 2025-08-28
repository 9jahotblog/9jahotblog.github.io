import re
import os
import json
import logging
import tempfile
import requests
import uuid
from datetime import datetime
from io import BytesIO
from dotenv import load_dotenv

import google.generativeai as genai
from google.generativeai import GenerativeModel
from telegram import Update, InputMediaPhoto
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from gtts import gTTS

# ------------------ Config ------------------

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

USERS_DB = "users.json"
STATS_DB = "stats.json"

# ------------------ Storage Helpers ------------------

def load_users():
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as f:
            return json.load(f)
    return []

def save_user(user_id, name):
    users = load_users()
    if user_id not in [u["id"] for u in users]:
        users.append({
            "id": user_id,
            "name": name,
            "joined": datetime.utcnow().isoformat()
        })
        with open(USERS_DB, "w") as f:
            json.dump(users, f, indent=2)

def increment_stat(stat_name):
    if not os.path.exists(STATS_DB):
        with open(STATS_DB, "w") as f:
            json.dump({}, f)
    with open(STATS_DB, "r") as f:
        stats = json.load(f)
    stats[stat_name] = stats.get(stat_name, 0) + 1
    with open(STATS_DB, "w") as f:
        json.dump(stats, f, indent=2)

def load_stats():
    if os.path.exists(STATS_DB):
        with open(STATS_DB, "r") as f:
            return json.load(f)
    return {}

# ------------------ Gemini Setup ------------------

genai.configure(api_key=GEMINI_API_KEY)
text_model = genai.GenerativeModel("models/gemini-2.0-flash")

# ------------------ Session Memory ------------------

chat_sessions = {}

# ------------------ Commands ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.full_name)
    await update.message.reply_text(
        "Hey {}, I’m Philadelphia, your AI co-pilot.\nCommands:\n"
        "- /philadelphia_vision <prompt>\n"
        "- /removebg (reply to photo)\n"
        "- /caption <text> (reply to photo)\n"
        "- /tts <text>\n"
        "- /audio_overview (then upload doc)\n"
        "- /statistics (admin)\n"
        "- /broadcast (admin)\n\n"
        "Just chat or ask questions, and I’ll answer with AI superpowers!"
        .format(user.first_name),
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Features:*\n"
        "- AI chat\n"
        "- Webpage summarization: send a link\n"
        "- /philadelphia_vision <prompt> (AI image gen)\n"
        "- /removebg (remove photo bg, reply to pic)\n"
        "- /caption <text> (caption image, reply to pic)\n"
        "- /tts <text> (text to speech)\n"
        "- /audio_overview (then upload doc for audio summary)\n"
        "- /statistics or /broadcast (admin)\n",
        parse_mode="Markdown"
    )

# ------------- 1. AI Image Generation -------------

async def philadelphia_vision_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
    if not context.args:
        await update.message.reply_text("Usage: /philadelphia_vision your prompt", parse_mode="Markdown")
        return
    prompt = " ".join(context.args)
    increment_stat("image_generations")
    try:
        response = requests.post(
            "https://api.stability.ai/v2beta/stable-image/generate/ultra",
            headers={
                "Authorization": f"Bearer {STABILITY_API_KEY}",
                "Accept": "image/*"
            },
            data={
                "prompt": prompt,
                "output_format": "png",
                "aspect_ratio": "1:1",
                "seed": "0"
            },
            files={"none": ""}
        )
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            draw = ImageDraw.Draw(image)
            watermark = "Philadelphia | https://t.me/writingurubot"
            font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), watermark, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((image.width - w - 20, image.height - h - 20), watermark, font=font, fill=(255, 255, 255, 200))
            output = BytesIO()
            image.convert("RGB").save(output, format="PNG")
            output.seek(0)
            await update.message.reply_photo(photo=output, caption=f"Generated by Philadelphia\nPrompt: {prompt}")
        else:
            await update.message.reply_text("Image generation failed. Try again later.")
    except Exception as e:
        logging.exception("Image generation error")
        await update.message.reply_text("Image generation failed.")

# ------------- 2. Remove Background -------------

async def removebg_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Reply to a photo with /removebg.")
        return
    photo = update.message.reply_to_message.photo[-1]
    file = await photo.get_file()
    img_path = os.path.join(tempfile.gettempdir(), f"removebg_{uuid.uuid4().hex}.jpg")
    await file.download_to_drive(custom_path=img_path)
    try:
        with open(img_path, "rb") as image_file:
            response = requests.post(
                "https://api.remove.bg/v1.0/removebg",
                files={"image_file": image_file},
                data={"size": "auto"},
                headers={"X-Api-Key": REMOVE_BG_API_KEY},
                timeout=30
            )
        if response.status_code == 200:
            output = BytesIO(response.content)
            output.seek(0)
            await update.message.reply_photo(photo=output, caption="Background removed!")
        else:
            await update.message.reply_text("Failed to remove background.")
    except Exception:
        await update.message.reply_text("Something went wrong.")
    finally:
        try: os.remove(img_path)
        except: pass

# ------------- 3. Image Caption -------------

async def caption_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to an image with:\n/caption Your caption here", parse_mode="Markdown")
        return
    caption_text = " ".join(context.args)
    image_msg = update.message.reply_to_message
    if not image_msg.photo:
        await update.message.reply_text("You must reply to an image.")
        return
    photo = image_msg.photo[-1]
    file = await photo.get_file()
    img_bytes = BytesIO()
    await file.download_to_memory(out=img_bytes)
    img_bytes.seek(0)
    try:
        image = Image.open(img_bytes).convert("RGB")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        font_size = max(24, image.width // 18)
        bbox = draw.textbbox((0, 0), caption_text, font=font)
        text_width = bbox[2] - bbox[0]
        position = ((image.width - text_width) // 2, image.height - font_size * 2)
        draw.text(position, caption_text, font=font, fill="white")
        output = BytesIO()
        image.save(output, format="JPEG")
        output.seek(0)
        await update.message.reply_photo(photo=output, caption="Here's your captioned image!")
    except Exception:
        await update.message.reply_text("Couldn’t generate the captioned image.")

# ------------- 4. TTS -------------

async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /tts <text>")
        return
    text = " ".join(context.args)
    try:
        tts = gTTS(text, lang="en")
        f = BytesIO()
        tts.write_to_fp(f)
        f.seek(0)
        await update.message.reply_voice(voice=f, caption=text)
    except Exception:
        await update.message.reply_text("TTS generation failed.")

# ------------- 5. Audio Overview (placeholder logic) -------------

awaiting_audio_summary = set()

async def audio_overview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting_audio_summary.add(user_id)
    await update.message.reply_text("Upload the document you'd like me to summarize with audio (feature available soon).")

# ------------- 6. Statistics -------------

async def statistics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to view statistics.")
        return
    stats = load_stats()
    msg = "📊 Statistics:\n"
    for k, v in stats.items():
        msg += f"- {k}: {v}\n"
    await update.message.reply_text(msg or "No usage yet.")

# ------------- 7. Broadcast -------------

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    users = load_users()
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message here", parse_mode="Markdown")
        return
    message = " ".join(context.args)
    count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u["id"], text=message)
            count += 1
        except Exception:
            continue
    await update.message.reply_text(f"Broadcasted to {count} users.")

# ------------- 8. AI-Powered Chat -------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    increment_stat("text_messages")
    user_id = update.effective_user.id
    url_match = re.search(r'(https?://\S+)', user_input)
    if url_match:
        url = url_match.group(1)
        await update.message.reply_text("Hold on, I’m reading that page…")
        try:
            page = requests.get(url, timeout=10)
            soup = BeautifulSoup(page.text, 'html.parser')
            raw_text = soup.get_text().strip()
            raw_text = raw_text[:3000] if len(raw_text) > 3000 else raw_text
            summary = text_model.generate_content(
                f"Summarize this webpage for me in plain English:\n\n{raw_text}"
            ).text.strip()
            if user_id not in chat_sessions:
                chat_sessions[user_id] = {"chat": text_model.start_chat(history=[]), "doc_context": ""}
            chat_sessions[user_id]["doc_context"] = summary
            await update.message.reply_text(f"Page Summary:\n{summary}")
            await update.message.reply_text("You can now ask me anything about that page.")
            return
        except Exception:
            await update.message.reply_text("Couldn't read or summarize that page, sorry.")
            return
    if user_id not in chat_sessions:
        chat_sessions[user_id] = {"chat": text_model.start_chat(history=[]), "doc_context": ""}
    response = chat_sessions[user_id]["chat"].send_message(user_input)
    reply = response.text.strip()
    await update.message.reply_text(reply[:4000])

# ------------- Registration -------------

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("philadelphia_vision", philadelphia_vision_command))
    app.add_handler(CommandHandler("removebg", removebg_command))
    app.add_handler(CommandHandler("caption", caption_command))
    app.add_handler(CommandHandler("tts", tts_command))
    app.add_handler(CommandHandler("audio_overview", audio_overview_command))
    app.add_handler(CommandHandler("statistics", statistics_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logging.info("Starting Philadelphia AI bot...")
    app.run_polling()

if __name__ == "__main__":
    main()
