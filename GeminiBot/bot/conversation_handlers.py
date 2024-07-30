import io
import os
import logging
import uuid
import math
import pickle
from functools import wraps


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import PIL.Image

from core import GeminiChat
from database.database import (
    create_conversation,
    get_user_conversation_count,
    select_conversations_by_user,
    select_conversation_by_id,
    delete_conversation_by_id,
)
from helpers.inline_paginator import InlineKeyboardPaginator
from helpers.helpers import conversations_page_content, strip_markdown
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CHOOSING, IMAGE_CHOICE, CONVERSATION, CONVERSATION_HISTORY = range(4)


def restricted(func):
    @wraps(func)
    async def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != int(os.getenv("AUTHORIZED_USER")):
            logger.info(f"Unauthorized access denied for {user_id}.")
            await update.message.reply_animation(
              "https://github.com/sudoAlireza/GeminiBot/assets/87416117/beeb0fd2-73c6-4631-baea-2e3e3eeb9319",
                caption="This is my personal Bot, to run your own Bot look at:\nhttps://github.com/Philipsmith6175/Philadelphia-",
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapped


@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation with /start command and ask the user for input."""
    query = update.callback_query
    logger.info("Received command: /start")

    keyboard = [
        [
            InlineKeyboardButton(
                "Start New Conversation", callback_data="New_Conversation"
            ),
            InlineKeyboardButton(
                "Image Description", callback_data="Image_Description"
            ),
        ],
        [InlineKeyboardButton("Chat History", callback_data="PAGE#1")],
     [
            InlineKeyboardButton("Chat History", callback_data="PAGE#1"),
            InlineKeyboardButton("Task", callback_data="Task"),
        ],
        [
            InlineKeyboardButton(
                "Set Description", callback_data="Set_Description"
            ),
            InlineKeyboardButton("Set Profile Pic", callback_data="Set_Profile_Pic"),
        ],
        [InlineKeyboardButton("Kick", callback_data="Kick")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text="Hi. It's Philadelphia Chat Bot. You can ask me anything and talk to me about whatever you want. Let's talk egbon!",
        reply_markup=reply_markup,
    )

    return CHOOSING


@restricted
async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE, conn) -> int:
    """Start the conversation with button and ask the user for input."""
    query = update.callback_query
    await query.answer()

    prev_message = context.user_data.get("to_delete_message")
    if prev_message:
        await context.bot.delete_message(
            chat_id=prev_message.chat_id, message_id=prev_message.id
        )
        context.user_data["to_delete_message"]

    try:
        user_details = query.from_user
        user_id = user_details.id
        conversation_id = context.user_data.get("conversation_id")
        gemini_chat: GeminiChat = context.user_data.get("gemini_chat")

        if gemini_chat or conversation_id:
            if "_SAVE" in query.data:
                conversation_history = gemini_chat.get_chat_history()
                conversation_title = gemini_chat.get_chat_title()

                conversation_id = conversation_id or f"conv{uuid.uuid4().hex[:6]}"
                with open(f"./pickles/{conversation_id}.pickle", "wb") as fp:
                    pickle.dump(conversation_history, fp)

                conv = (
                    conversation_id,
                    user_id,
                    conversation_title,
                )
                create_conversation(conn, conv)
                logger.info(f"conversation {conversation_id} saved in db and closed")

            else:
                logger.info(f"conversation {conversation_id} closed without saving")

            gemini_chat.close()
        else:
            logger.info("No active chat to close")

        gemini_chat = None
        context.user_data["gemini_chat"] = None
        context.user_data["conversation_id"] = None

    except Exception as e:
        logger.error("Error during conversation handling: %s", e)

    keyboard = [
        [
            InlineKeyboardButton(
                "Start New Conversation", callback_data="New_Conversation"
            )
        ],
        [InlineKeyboardButton("Image Description", callback_data="Image_Description")],
        [InlineKeyboardButton("Chat History", callback_data="PAGE#1")],
        [InlineKeyboardButton("Start Again", callback_data="Start_Again")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(
        query.message.chat.id,
        text="Hi. It's Philadelphia Chat Bot. You can ask me anything and talk to me about what you want",
        reply_markup=reply_markup,
    )
    context.user_data["to_delete_message"] = msg

    return CHOOSING


@restricted
async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user to start conversation by writing any message."""
    query = update.callback_query
    await query.answer()

    logger.info("Received callback: New_Conversation")
    message_content = "You asked for a conversation. OK, Let's start conversation Egbon!"

    conv_id = context.user_data.get("conversation_id")
    if conv_id:
        message_content = "You asked for a continuous  conversation. OK, Let's go Chief!"

    keyboard = [[InlineKeyboardButton("Return to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await query.edit_message_text(
        text=message_content,
        reply_markup=reply_markup,
    )
    context.user_data["to_delete_message"] = msg

    return CONVERSATION


@restricted
async def reply_and_new_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Send user message to Gemini core and respond and wait for new message or exit command"""
    query = update.callback_query

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        text="Typing...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )

    ##############

    text = update.message.text
    conv_id = context.user_data.get("conversation_id")
    conversation_history = []
    if conv_id:
        with open(f"./pickles/{conv_id}.pickle", "rb") as fp:
            conversation_history = pickle.load(fp)

    gemini_chat = context.user_data.get("gemini_chat")
    if not gemini_chat:
        logger.info("Creating new conversation instance")
        gemini_chat = GeminiChat(
            gemini_token=os.getenv("GEMINI_API_TOKEN"),
            chat_history=conversation_history,
        )
        gemini_chat.start_chat()

    response = gemini_chat.send_message(text).encode("utf-8").decode("utf-8", "ignore")

    context.user_data["gemini_chat"] = gemini_chat

    keyboard = [
        [
            InlineKeyboardButton(
                "Save and Back to menu", callback_data="Start_Again_SAVE"
            )
        ],
        [
            InlineKeyboardButton(
                "Back to menu without saving", callback_data="Start_Again"
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            text=response,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            chat_id=update.message.chat_id,
        )
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.id)

    except Exception as e:
        await context.bot.send_message(
            text=strip_markdown(response),
            reply_markup=reply_markup,
            chat_id=update.message.chat_id,
        )
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.id)
        logging.warning(__name__, e)

    return CONVERSATION


@restricted
async def get_conversation_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, conn
) -> int:
    """Get conversation from database and ask user if wants new conversation or not"""

    query_messsage = update.message.text.replace("/", "")
    context.user_data["conversation_id"] = query_messsage
    user_details = update.message.from_user.id
    conv_specs = (user_details, query_messsage)

    conversation = select_conversation_by_id(conn, conv_specs)

    message_content = f"Conversation {conversation.get('conv_id')} retrieved and title is: {conversation.get('title')}"

    keyboard = [
        [
            InlineKeyboardButton(
                "Continue Conversations", callback_data="New_Conversation"
            )
        ],
        [
            InlineKeyboardButton(
                "Delete Conversation", callback_data="Delete_Conversation"
            )
        ],
        [InlineKeyboardButton("Back to menu", callback_data="Start_Again")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await update.message.reply_text(
        text=message_content, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
    )
    context.user_data["to_delete_message"] = msg

    return CONVERSATION_HISTORY


@restricted
async def delete_conversation_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE, conn
) -> int:
    """Delete conversation if user clicks on Delete button"""
    query = update.callback_query

    await query.answer()

    conversation_id = context.user_data["conversation_id"]
    user_details = query.from_user.id
    conv_specs = (user_details, conversation_id)

    conversation = delete_conversation_by_id(conn, conv_specs)

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await query.edit_message_text(
        text="Conversation history deleted successfully. Back to menu to Start new Conversation!",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["to_delete_message"] = msg

    return CHOOSING


@restricted
async def start_image_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Ask user to upload an image with caption"""
    query = update.callback_query
    logger.info("Received callback: Image_Description")

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await query.edit_message_text(
        f"You asked for me to describe an Image. OK, Send an image with a caption AGBA!",
        reply_markup=reply_markup,
    )
    context.user_data["to_delete_message"] = msg

    return IMAGE_CHOICE


@restricted
async def generate_text_from_image(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Send image to Gemini core and send response to user"""
    query = update.callback_query
    logger.info("Received callback: generate_text_from_image")

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await update.message.reply_text(
        text="Analysing image...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )

    photo_file = await update.message.photo[-1].get_file()
    buf = io.BytesIO()
    await photo_file.download_to_memory(buf)
    buf.name = "user_image.jpg"
    buf.seek(0)

    image = PIL.Image.open(buf)

    gemini_image_chat = GeminiChat(
        gemini_token=os.getenv("GEMINI_API_TOKEN"), image=image
    )

    try:
        response = response = (
            gemini_image_chat.send_image(update.message.caption)
            .encode("utf-8")
            .decode("utf-8", "ignore")
        )

        if not response:
            raise Exception("Empty response from Gemini")
    except Exception as e:
        logger.warning("Error during image processing: %s", e)
        response = "Couldn't describe the photo. Please try again."

    buf.close()
    del photo_file
    del image

    keyboard = [[InlineKeyboardButton("Back to menu", callback_data="Start_Again")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            text=response,
            parse_mode="Markdown",
            reply_markup=reply_markup,
            chat_id=update.message.chat_id,
        )
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.id)

    except Exception as e:
        await context.bot.send_message(
            text=strip_markdown(response),
            reply_markup=reply_markup,
            chat_id=update.message.chat_id,
        )
        await context.bot.delete_message(chat_id=msg.chat_id, message_id=msg.id)
        logging.warning(__name__, e)

    return CHOOSING


@restricted
async def get_conversation_history(
    update: Update, context: ContextTypes.DEFAULT_TYPE, conn
) -> int:
    """Read conversations history of the user"""
    query = update.callback_query
    await query.answer()
    logger.info("Received callback: PAGE#")

    conversations_count = get_user_conversation_count(conn, query.from_user.id)
    total_pages = math.ceil(float(conversations_count / 10))

    page_number = int(query.data.split("#")[1])
    offset = (page_number - 1) * 10

    conversations = select_conversations_by_user(conn, (query.from_user.id, offset))
    if conversations:
        page_content = conversations_page_content(conversations)
    else:
        page_content = "You have no chat history Egbon!"

    paginator = InlineKeyboardPaginator(
        total_pages, current_page=page_number, data_pattern="PAGE#{page}"
    )
    paginator.add_after(
        InlineKeyboardButton("Back to menu", callback_data="Start_Again")
    )

    msg = await query.edit_message_text(
        page_content,
        reply_markup=paginator.markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data["to_delete_message"] = msg

    return CONVERSATION_HISTORY


@restricted
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End the conversation."""
    # To-Do: Remove this handler and handle ending with start and start_over handlers
    query = update.callback_query
    logger.info("Received callback: Done")

    try:
        user_data = context.user_data
        gemini_chat = user_data["gemini_chat"]

        gemini_chat.close()
    except:
        pass

    user_data["gemini_chat"] = None

    keyboard = [
        [
            InlineKeyboardButton(
                "Start New Conversation", callback_data="New_Conversation"
            )
        ],
        [InlineKeyboardButton("Image Description", callback_data="Image_Description")],
        [InlineKeyboardButton("Refresh", callback_data="Start_Again")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message("Until next time!", reply_markup=reply_markup)

    user_data.clear()
    return CHOOSING

@restricted
async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /task command."""
    chat_id = update.callback_query.message.chat_id
    task_text = "You can write lengthy texts using this command."
    await bot.send_message(chat_id=chat_id, text=task_text)
    return CHOOSING


@restricted
async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /setdescription command."""
    chat_id = update.callback_query.message.chat_id
    description_text = "You can set the group description using this command."
    await bot.send_message(chat_id=chat_id, text=description_text)
    return CHOOSING


@restricted
async def set_profile_pic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /setprofilepic command."""
    chat_id = update.callback_query.message.chat_id
    profile_pic_text = "You can set the group profile picture using this command."
    await bot.send_message(chat_id=chat_id, text=profile_pic_text)
    return CHOOSING


@restricted
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /kick command."""
    chat_id = update.callback_query.message.chat_id
    kick_text = "You can kick a user out of the group using this command."
    await bot.send_message(chat_id=chat_id, text=kick_text)
    return CHOOSING


@restricted
async def ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /ai command."""
    chat_id = update.callback_query.message.chat_id
    ai_text = "You can learn about another AI using this command."
    await bot.send_message(chat_id=chat_id, text=ai_text)
    return CHOOSING


@restricted
async def developer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /developer command."""
    chat_id = update.callback_query.message.chat_id
    developer_text = "You can get in touch with my developer using this command."
    await bot.send_message(chat_id=chat_id, text=developer_text)
    return CHOOSING


@restricted
async def greeting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the greeting messages."""
    chat_id = update.callback_query.message.chat_id
    user_message = update.message.text.lower()
    greetings = ["who is your creator", "who created you", "who made you"]
    if any(keyword in user_message for keyword in greetings):
        await bot.send_message(chat_id=chat_id, text="I was created by Kolade Philip Ogunlana.")
    elif any(keyword in user_message for keyword in ["what is your name", "what's your name", "what can I call you"]):
        await bot.send_message(chat_id=chat_id, text="You can call me Philadelphia!")
    # Add more greetings handling here (optional)
    return CHOOSING