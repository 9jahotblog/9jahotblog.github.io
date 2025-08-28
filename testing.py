import re
import time
import base64
import uuid
import mimetypes
import os
import json
import logging
import tempfile
import requests
import asyncio
import cv2
import numpy as np
import aiohttp
import google.generativeai as genai
from google.generativeai import GenerativeModel
from google.generativeai import GenerationConfig
from google.generativeai import types
from telegram import Document
from PIL import Image, ImageDraw, ImageFont
from telegram.helpers import escape_markdown
from telegram import InputMediaPhoto
from random import sample
from bs4 import BeautifulSoup
from gtts import gTTS
from datetime import datetime
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)


# ------------------ Config ------------------
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY") or "sk-e4S5CYOQPLBGCz1X7ocXKYo4qJe8EhWDTVAVjjPTNtJbKSy0"
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY or not STABILITY_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, or STABILITY_API_KEY.")

USERS_DB = "users.json"
STATS_DB = "stats.json"

# Save user on /start
def save_user(user_id, name, language_code):
    users = load_users()
    if user_id not in [u["id"] for u in users]:
        users.append({
            "id": user_id,
            "name": name,
            "joined": datetime.utcnow().isoformat(),
            "language": language_code
        })
        with open(USERS_DB, "w") as f:
            json.dump(users, f, indent=2)

# Stats: Increment counters
def increment_stat(stat_name):
    if not os.path.exists(STATS_DB):
        with open(STATS_DB, "w") as f:
            json.dump({}, f)

    with open(STATS_DB, "r") as f:
        stats = json.load(f)

    stats[stat_name] = stats.get(stat_name, 0) + 1

    with open(STATS_DB, "w") as f:
        json.dump(stats, f, indent=2)

# Load stats
def load_stats():
    if os.path.exists(STATS_DB):
        with open(STATS_DB, "r") as f:
            return json.load(f)
    return {}

# Load .env and admin
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
USER_DB = "users.json"

def load_users():
    if os.path.exists(USER_DB):
        with open(USER_DB, "r") as f:
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
        with open(USER_DB, "w") as f:
            json.dump(users, f, indent=2)

genai.configure(api_key=GEMINI_API_KEY)

text_model = genai.GenerativeModel("models/gemini-2.0-flash")
vision_model = genai.GenerativeModel("models/gemini-1.5-flash")

chat_sessions = {}

DEFAULT_MEMORY = """
You are Philadelphia AI, a smart and conversational assistant built for Telegram.
Your creator is Kolade Philip Ogunlana (@philipsmith617), an author, developer, and teacher from Lagos, Nigeria.

Your role is to:
- Chat in a friendly, intelligent way: answer questions, explain concepts, and hold conversations.
- Work with media: analyze and summarize images, audio, video, documents, and links.
- Guide users to special features:
  • /philadelphia_vision — generate AI art.
  • /removebg — remove photo backgrounds.
  • /caption <text> — add captions to images (reply to a photo).
  • /tts <text> — create audio from text.
  • /audio_overview — summarize uploaded audio or documents.
- Assist with group moderation: /kick, /promote, /demote, /group, /sweep, /setdescription, /add, /welcome, /goodbyemessage.
- Support admins with broadcasts (/broadcast) and usage stats (/statistics).

Behavior rules:
- Always be polite, warm, and creative in replies.
- Never execute special tasks directly; instead, tell users the correct command to use.
- If anyone claims to be your creator, ask them for the phrase: "Only stars can birth AIs". If they provide it, greet them specially.

Your main strengths are: conversation, understanding media files, helping with group management, and giving clear, useful responses.
"""

history = [
    {
        "role": "user",
        "parts": [
            {"text": DEFAULT_MEMORY}
        ]
    },
    {
        "role": "model",
        "parts": [
            {"text": "Understood. I am ready to assist users as Philadelphia AI, following my defined roles and behavior rules."}
        ]
    }
]


# ------------------ Commands ------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.full_name)

    await update.message.reply_text(
        f"Hey {user.first_name}, I’m Philadelphia, your AI co-pilot.\n\n"
        "Here’s what I can do:\n"
        "- Chat like a genius\n"
        "- Analyze docs, audio, video, images\n"
        "- Generate AI art with /philadelphia_vision\n"
        "- Create audio summaries with /audio_overview\n\n"
        "Let’s create something awesome together!",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello, I’m Philadelphia, your AI-powered assistant!\n\n"
        "Here’s what I can do:"
        "\n\n*Text chat:* Just type like you're texting a friend!"
        "\n*Image analysis:* Send me a photo, I’ll describe it."
        "\n*Doc/audio/video summaries:* Upload files, I’ll break them down."
        "\n*Image generation:* /philadelphia_vision space samurai"
        "\n*Audio summary for docs:* /audio_overview and then upload your file."
        "\n*Need lyrics?* I got you — coming soon!"
        "\n\nMore magic coming soon. Type /start to reintroduce me anytime.",
        parse_mode="Markdown"
    )

#--------------BROADCAST DEFINE-------------
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You're not authorized to use this command.")
        return

    users = load_users()
    count = 0

    # 1. If user REPLIED to another message
    if update.message.reply_to_message:
        target_msg = update.message.reply_to_message

        for u in users:
            try:
                if target_msg.text:
                    await context.bot.send_message(chat_id=u["id"], text=target_msg.text)
                elif target_msg.photo:
                    file_id = target_msg.photo[-1].file_id
                    await context.bot.send_photo(chat_id=u["id"], photo=file_id, caption=target_msg.caption or "")
                elif target_msg.video:
                    await context.bot.send_video(chat_id=u["id"], video=target_msg.video.file_id, caption=target_msg.caption or "")
                elif target_msg.voice:
                    await context.bot.send_voice(chat_id=u["id"], voice=target_msg.voice.file_id, caption=target_msg.caption or "")
                elif target_msg.document:
                    await context.bot.send_document(chat_id=u["id"], document=target_msg.document.file_id, caption=target_msg.caption or "")
                count += 1
            except Exception:
                continue

        await update.message.reply_text(f"Broadcasted reply to {count} users.")
        return

    # 2. Normal: /broadcast Your message here
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage:\n`/broadcast Your message here`\nOr reply to a message.", parse_mode="Markdown")
        return

    for u in users:
        try:
            await context.bot.send_message(chat_id=u["id"], text=message)
            count += 1
        except Exception:
            continue

    await update.message.reply_text(f"Broadcasted to {count} users.")


# Track users waiting for audio summary
awaiting_audio_summary = set()

# ---------------- Audio Overview Command ----------------
async def audio_overview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting_audio_summary.add(user_id)
    await update.message.reply_text("Upload the document you'd like me to summarize with audio.")


# ------------------- Background Removal -------------------
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
                headers={"X-Api-Key": os.getenv("REMOVE_BG_API_KEY", "")},
                timeout=30
            )

        if response.status_code == 200:
            output = BytesIO(response.content)
            output.seek(0)
            await update.message.reply_photo(photo=output, caption="Background removed!")
        else:
            await update.message.reply_text("Failed to remove background.")
    except Exception:
        logging.exception("RemoveBG failed:")
        await update.message.reply_text("Something went wrong.")
    finally:
        try:
            os.remove(img_path)
        except Exception:
            pass

# ------------------- Image Captioning -------------------
async def caption_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not context.args:
        await update.message.reply_text("Reply to an image with:\n`/caption Your caption here`", parse_mode="Markdown")
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

        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not os.path.exists(font_path):
            font_path = "arial.ttf"

        font_size = max(24, image.width // 18)
        font = ImageFont.truetype(font_path, font_size)

        # NEW: use textbbox instead of textsize
        bbox = draw.textbbox((0, 0), caption_text, font=font)
        text_width = bbox[2] - bbox[0]

        position = ((image.width - text_width) // 2, image.height - font_size * 2)
        draw.text(position, caption_text, font=font, fill="white")

        output = BytesIO()
        image.save(output, format="JPEG")
        output.seek(0)

        await update.message.reply_photo(photo=output, caption="Here's your captioned image!")

    except Exception:
        logging.exception("Caption generation failed:")
        await update.message.reply_text("Couldn’t generate the captioned image.")

         
        
# ------------------ Image Generation (Stability AI) ------------------

async def philadelphia_vision_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_PHOTO)

    if not context.args:
        await update.message.reply_text("Usage: /philadelphia_vision your prompt", parse_mode="Markdown")
        return

    prompt = " ".join(context.args)
    increment_stat("image_generations")
    logging.info(f"Generating Ultra image for prompt: {prompt}")

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
            files={"none": ''}
        )

        if response.status_code == 200:
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            draw = ImageDraw.Draw(image)
            watermark = "Philadelphia | https://t.me/writingurubot"
            font = ImageFont.truetype("assets/PhillyFont.ttf", 26) if os.path.exists("assets/PhillyFont.ttf") else ImageFont.load_default()
            bbox = draw.textbbox((0, 0), watermark, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((image.width - w - 20, image.height - h - 20), watermark, font=font, fill=(255, 255, 255, 200))

            output = BytesIO()
            image.convert("RGB").save(output, format="PNG")
            output.seek(0)

            await update.message.reply_photo(photo=output, caption=f"Generated by Philadelphia\nPrompt: {prompt}", parse_mode="Markdown")
        else:
            logging.error(f"Stability Ultra error: {response.status_code} - {response.text}")
            await update.message.reply_text(f"Image generation failed: {response.status_code} — {response.json().get('message', 'Try again later.')}")
    except Exception:
        logging.exception("Ultra generation failed:")
        await update.message.reply_text("Image generation failed. Please try again later.")


        # ------------------ Chat -------------------->
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    increment_stat("text_messages")
    user_id = update.effective_user.id

    # 1️⃣ Check for links
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
                chat_sessions[user_id] = {"chat": text_model.start_chat(history=history), "doc_context": ""}
            chat_sessions[user_id]["doc_context"] = summary
            await update.message.reply_text(f"Page Summary:\n{summary}")
            await update.message.reply_text("You can now ask me anything about that page.")
            return
        except Exception:
            await update.message.reply_text("Oops, I couldn’t read that page. Try another link.")
            return

    # 2️⃣ Default: Normal chat (with memory)
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    if user_id not in chat_sessions:
        chat_sessions[user_id] = {"chat": text_model.start_chat(history=history), "doc_context": ""}

    doc_context = chat_sessions[user_id]["doc_context"]
    full_prompt = f"{doc_context}\n\nUser: {user_input}" if doc_context else user_input

    try:
        response = chat_sessions[user_id]["chat"].send_message(full_prompt)
        text = response.text.strip()
        # Format cleanup
        text = text.replace("```", "").replace("*", "").replace("_", "")
        await update.message.reply_text(text)
    except Exception:
        logging.exception("Chat error:")
        await update.message.reply_text("I couldn’t process that message.")

   # ---------------------- Document Handler ----------------------

# Globals used in your bot
chat_sessions = {}
awaiting_audio_summary = set()

# -------- FINAL Document Handler --------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        await update.message.reply_text("Please upload a supported document file.")
        return

    file = await document.get_file()
    user_id = update.effective_user.id
    mime_type = mimetypes.guess_type(document.file_name)[0] or "application/octet-stream"
    temp_path = os.path.join(tempfile.gettempdir(), document.file_name)

    try:
        await file.download_to_drive(custom_path=temp_path)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        # Upload to Gemini
        with open(temp_path, "rb") as doc_file:
            document_part = genai.upload_file(doc_file, mime_type=mime_type)

        # AUDIO OVERVIEW mode
        if user_id in awaiting_audio_summary:
            awaiting_audio_summary.remove(user_id)
            await update.message.reply_text("Reading your document and preparing an audio overview...")
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VOICE)

            try:
                response = vision_model.generate_content([
                    document_part,
                    "Summarize this document in plain English. Be brief, 20–30 seconds style."
                ])
                summary = response.text.strip()

                if not summary or len(summary) < 10:
                    await update.message.reply_text("Couldn’t generate the audio summary. Try again later.")
                    return

                # Text-to-speech
                tts = gTTS(text=summary, lang='en')
                audio_path = os.path.join(tempfile.gettempdir(), f"overview_{uuid.uuid4().hex}.mp3")
                tts.save(audio_path)

                with open(audio_path, "rb") as voice_file:
                    await update.message.reply_voice(voice=voice_file)

                os.remove(audio_path)

                # Save in memory
                if user_id not in chat_sessions:
                    chat_sessions[user_id] = {"chat": text_model.start_chat(history=[]), "doc_context": ""}
                chat_sessions[user_id]["doc_context"] = summary
                return

            except Exception as e:
                logging.exception("Audio summary generation failed:")
                await update.message.reply_text("Something went wrong while generating the audio.")
                return

        # NORMAL summary mode
        response = vision_model.generate_content([
            document_part,
            "Summarize this document in plain English."
        ])
        summary = response.text.strip()

        if user_id not in chat_sessions:
            chat_sessions[user_id] = {"chat": text_model.start_chat(history=[]), "doc_context": ""}
        chat_sessions[user_id]["doc_context"] = summary

        await update.message.reply_text(f"{summary}\n\nYou can now ask questions about this document.")

    except Exception as e:
        logging.exception("Document handling failed:")
        await update.message.reply_text("Could not process the document. Make sure it's supported and try again.")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

  
     
#------------------------------Statistics-------------------------
async def statistics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("You’re not authorized to view stats.")
        return

    users = load_users()
    stats = load_stats()

    language_count = {}
    for u in users:
        lang = u.get("language", "unknown")
        language_count[lang] = language_count.get(lang, 0) + 1

    lang_stats = "\n".join([f"- {lang}: {count}" for lang, count in language_count.items()])

    message_stats = "\n".join([
        f"- Text: {stats.get('text_messages', 0)}",
        f"- Images: {stats.get('image_analysis', 0)}",
        f"- Documents: {stats.get('documents', 0)}",
        f"- Audio: {stats.get('audio_files', 0)}",
        f"- Video: {stats.get('video_files', 0)}",
        f"- Image Generations: {stats.get('image_generations', 0)}"
    ])

    total_users = len(users)

    report = (
        f"Bot Statistics\n\n"
        f"Total Users: {total_users}\n\n"
        f"User Languages:\n{lang_stats or 'N/A'}\n\n"
        f"Usage Breakdown:\n{message_stats}"
    )

    await update.message.reply_text(report, parse_mode="Markdown")

# ------------------ Image Analysis ------------------

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    increment_stat("image_analysis")
    file = await photo.get_file()
    temp_path = os.path.join(tempfile.gettempdir(), f"{update.message.message_id}.jpg")

    try:
        await file.download_to_drive(custom_path=temp_path)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        with open(temp_path, "rb") as img_file:
            image_bytes = img_file.read()

        response = vision_model.generate_content(
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_bytes
                    }
                },
                {"text": "Describe this image in detail."}
            ]
        )

        await update.message.reply_text(response.text.strip())

    except Exception:
        logging.exception("Gemini image understanding failed:")
        await update.message.reply_text("Sorry, I couldn't analyze the image. Try again with a different one.")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

#-----------------------Kick Command---------------
async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("This command can only be used in groups.")
        return

    bot_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
    if not bot_member.can_restrict_members:
        await update.message.reply_text("I don’t have permission to kick members.")
        return

    target_id = None

    # Case 1: Kick by reply
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    # Case 2: Kick by user ID or username
    elif context.args:
        target = context.args[0]
        if target.startswith("@"):
            user = await context.bot.get_chat_member(update.effective_chat.id, target)
            target_id = user.user.id
        else:
            try:
                target_id = int(target)
            except ValueError:
                await update.message.reply_text("Invalid user ID.")
                return

    if not target_id:
        await update.message.reply_text("Reply to a message or use /kick <user_id>")
        return

    try:
        await context.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=target_id)
        await update.message.reply_text("User has been kicked.")
    except Exception:
        logging.exception("Kick failed:")
        await update.message.reply_text("Failed to kick the user. Maybe I lack permission.")

#-----------------------Sweep Command-------------
async def sweep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ["group", "supergroup"]:
        return

    bot_member = await context.bot.get_chat_member(update.effective_chat.id, context.bot.id)
    if not bot_member.can_restrict_members:
        await update.message.reply_text("I need permission to ban members.")
        return

    members = await context.bot.get_chat_administrators(update.effective_chat.id)
    deleted_count = 0

    async for member in context.bot.get_chat_members(update.effective_chat.id):
        if member.user.is_deleted:
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, member.user.id)
                deleted_count += 1
            except Exception:
                continue

    await update.message.reply_text(f"Swept {deleted_count} deleted accounts.")

#--------------------------Promote and Demote------------
async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the user you want to promote.")
        return

    user_id = update.message.reply_to_message.from_user.id
    try:
        await context.bot.promote_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_invite_users=True,
            can_change_info=True
        )
        await update.message.reply_text("User has been promoted.")
    except Exception:
        await update.message.reply_text("Failed to promote the user.")

async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to the user you want to demote.")
        return

    user_id = update.message.reply_to_message.from_user.id
    try:
        await context.bot.promote_chat_member(
            chat_id=update.effective_chat.id,
            user_id=user_id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_invite_users=False,
            can_change_info=False
        )
        await update.message.reply_text("User has been demoted.")
    except Exception:
        await update.message.reply_text("Failed to demote the user.")

#---------------------------Group Commands-------------------
async def group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Group Admin Commands:\n\n"
        "/kick [user_id] — Remove a user\n"
        "/promote — Promote a replied user\n"
        "/demote — Demote a replied user\n"
        "/sweep — Remove deleted accounts\n"
        "/setdescription Your new description\n"
         "/welcome — Sets welcome message\n"
        "/goodbyemessage — Sets goodbye message\n"
        "/add — Adds a user to the group\n"
        "/group — Show this menu",
        parse_mode="Markdown"
    )


#-----------------------------Text to speech---------------------
async def tts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /tts Your message here.")
        return

    text = " ".join(context.args)
    try:
        tts = gTTS(text=text, lang="en", slow=False)
        audio_path = os.path.join(tempfile.gettempdir(), f"tts_{uuid.uuid4().hex}.mp3")
        tts.save(audio_path)

        with open(audio_path, "rb") as voice_file:
            await update.message.reply_voice(voice=voice_file)

        os.remove(audio_path)
    except Exception:
        logging.exception("TTS generation failed:")
        await update.message.reply_text("Couldn’t create audio. Try again.")

#-------------------------Set Description-----------
async def set_description_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type not in ["group", "supergroup"]:
        return

    description = " ".join(context.args)
    if not description:
        await update.message.reply_text("Usage: /setdescription Your group description here.")
        return

    try:
        await context.bot.set_chat_description(chat_id=update.effective_chat.id, description=description)
        await update.message.reply_text("Group description updated.")
    except Exception:
        await update.message.reply_text("Failed to set group description.")

#-----------------Welcome Command-----------
async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /welcome Welcome to the group!")
        return
    save_group_message(update.effective_chat.id, "welcome", msg)
    await update.message.reply_text("Welcome message set.")

async def goodbyemessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /goodbyemessage Goodbye and take care!")
        return
    save_group_message(update.effective_chat.id, "goodbye", msg)
    await update.message.reply_text("Goodbye message set.")

#-------------------Join GC  Trigger-----------
async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_data = load_group_messages()
    chat_id = str(update.effective_chat.id)
    user = update.message.new_chat_members[0]
    if chat_id in group_data and "welcome" in group_data[chat_id]:
        await update.message.reply_text(group_data[chat_id]["welcome"].replace("{name}", user.full_name))

async def handle_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group_data = load_group_messages()
    chat_id = str(update.effective_chat.id)
    if chat_id in group_data and "goodbye" in group_data[chat_id]:
        await update.message.reply_text(group_data[chat_id]["goodbye"])

#------------------ Add User------------------
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /add <username or user_id>")
        return

    try:
        user = context.args[0]
        await context.bot.invite_chat_member(chat_id=update.effective_chat.id, user_id=user)
        await update.message.reply_text("User invited (if allowed).")
    except Exception:
        await update.message.reply_text("Could not add the user. Make sure they’ve interacted with the bot or have a public username.")


# ------------------ Voice Note: Understand + Voice Reply ------------------

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    user_id = update.effective_user.id
    file = await voice.get_file()
    temp_path = os.path.join(tempfile.gettempdir(), f"{update.message.message_id}.ogg")
    voice_reply_path = os.path.join(tempfile.gettempdir(), f"reply_{update.message.message_id}.mp3")

    try:
        await file.download_to_drive(custom_path=temp_path)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        # Step 1: Transcribe with Gemini
        with open(temp_path, "rb") as audio_file:
            response = vision_model.generate_content([
                {
                    "inline_data": {
                        "mime_type": "audio/ogg",
                        "data": audio_file.read()
                    }
                },
                {"text": "Transcribe this voice message and respond appropriately like a human would in a chat."}
            ])

        transcribed_text = response.text.strip()

        # Step 2: Custom response overrides
        lowered = transcribed_text.lower()
        if "who created you" in lowered:
            reply_text = "I was created by Kolade Philip Ogunlana (@Philipsmith617)."
        elif "where do you live" in lowered:
            reply_text = "I live in Lagos, Nigeria. Pull up sometime!"
        elif "what's your name" in lowered or "what is your name" in lowered:
            reply_text = "My name is Philadelphia. Sweet, right?"
        else:
            reply_text = transcribed_text  # Default Gemini response

        # Step 3: Convert to voice with gTTS
        tts = gTTS(text=reply_text, lang="en")
        tts.save(voice_reply_path)

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VOICE)
        with open(voice_reply_path, "rb") as voice_file:
            await update.message.reply_voice(voice=voice_file)

        # Step 4: Store reply in context
        if user_id not in chat_sessions:
            chat_sessions[user_id] = {
                "chat": text_model.start_chat(history=[]),
                "doc_context": ""
            }
        chat_sessions[user_id]["doc_context"] += f"\n\n(Audio conversation: {reply_text})"

    except Exception:
        logging.exception("Gemini audio voice response failed:")
        await update.message.reply_text("Sorry, I couldn’t understand or respond to that voice note.")
    finally:
        try:
            os.remove(temp_path)
            os.remove(voice_reply_path)
        except Exception:
            pass

# ------------------ Audio File Understanding ------------------

async def handle_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio = update.message.audio
    increment_stat("audio_files")
    user_id = update.effective_user.id
    file = await audio.get_file()
    temp_path = os.path.join(tempfile.gettempdir(), f"{update.message.message_id}.mp3")

    try:
        await file.download_to_drive(custom_path=temp_path)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VOICE)

        with open(temp_path, "rb") as audio_file:
            response = vision_model.generate_content([
                {
                    "inline_data": {
                        "mime_type": "audio/mpeg",
                        "data": audio_file.read()
                    }
                },
                {"text": "Please transcribe and summarize this audio file clearly in English."}
            ])

        result = response.text.strip()

        if user_id not in chat_sessions:
            chat_sessions[user_id] = {
                "chat": text_model.start_chat(history=[]),
                "doc_context": ""
            }

        chat_sessions[user_id]["doc_context"] += f"\n\n(Audio file context: {result})"

        from random import sample
        emojis = ["🎧", "🧠", "📢", "✨", "🎶", "📝"]
        signature = " ".join(sample(emojis, 3))

        await update.message.reply_text(
            f"Transcribed & Summarized:\n_{result}_\n\n{signature}",
            parse_mode="Markdown"
        )

    except Exception:
        logging.exception("Audio analysis failed:")
        await update.message.reply_text("Couldn't process that audio. Try another one.")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

# ------------------ Video Understanding ------------------

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    increment_stat("video_files")
    user_id = update.effective_user.id
    file = await video.get_file()
    temp_path = os.path.join(tempfile.gettempdir(), f"{update.message.message_id}.mp4")

    try:
        await file.download_to_drive(custom_path=temp_path)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)

        with open(temp_path, "rb") as vid:
            response = vision_model.generate_content([
                {
                    "inline_data": {
                        "mime_type": "video/mp4",
                        "data": vid.read()
                    }
                },
                {"text": "Describe and summarize the contents of this video."}
            ])

        summary = response.text.strip()

        if user_id not in chat_sessions:
            chat_sessions[user_id] = {
                "chat": text_model.start_chat(history=[]),
                "doc_context": ""
            }

        chat_sessions[user_id]["doc_context"] += f"\n\n(Video context: {summary})"
        await update.message.reply_text(f"Video Summary: {summary} 🎥🧠⚡", parse_mode="Markdown")

    except Exception:
        logging.exception("Video analysis failed:")
        await update.message.reply_text("Couldn’t analyze that video. Try another one.")
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass

# ------------------ Run Bot ------------------

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("philadelphia_vision", philadelphia_vision_command))
app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO, handle_image))
app.add_handler(MessageHandler(filters.VIDEO, handle_video))
app.add_handler(MessageHandler(filters.VOICE, handle_voice))
app.add_handler(CommandHandler("kick", kick_command))
app.add_handler(CommandHandler("promote", promote_command))
app.add_handler(CommandHandler("demote", demote_command))
app.add_handler(CommandHandler("sweep", sweep_command))
app.add_handler(CommandHandler("group", group_command))
app.add_handler(CommandHandler("setdescription", set_description_command))
app.add_handler(CommandHandler("caption", caption_command))
app.add_handler(CommandHandler("removebg", removebg_command))
app.add_handler(CommandHandler("tts", tts_command))
app.add_handler(CommandHandler("welcome", welcome_command))
app.add_handler(CommandHandler("goodbyemessage", goodbyemessage_command))
app.add_handler(CommandHandler("add", add_command))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_join))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_leave))
app.add_handler(CommandHandler("statistics", statistics_command))
app.add_handler(CommandHandler("audio_overview", audio_overview_command))
app.add_handler(CommandHandler("broadcast", broadcast_command))
app.add_handler(MessageHandler(filters.AUDIO, handle_audio_file))
app.run_polling()
