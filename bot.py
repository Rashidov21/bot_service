import os
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

API_BASE = os.getenv("API_BASE", "").rstrip("/")
BOT_API_TOKEN = os.getenv("BOT_API_TOKEN", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")


def api_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


def fetch_meta() -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/api/bot/meta/", headers=api_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_category_keyboard(categories: List[Dict[str, Any]]):
    buttons = [
        [InlineKeyboardButton(c["title"], callback_data=f"cat:{c['slug']}")]
        for c in categories
    ]
    return InlineKeyboardMarkup(buttons)


def build_tag_keyboard(tags: List[Dict[str, Any]], selected: List[str]):
    buttons = []
    for t in tags:
        checked = "✅ " if t["slug"] in selected else ""
        buttons.append(
            [InlineKeyboardButton(f"{checked}{t['title']}", callback_data=f"tag:{t['slug']}")]
        )
    buttons.append([InlineKeyboardButton("Tayyor", callback_data="tag:done")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = "title"
    await update.message.reply_text("Sarlavhani yuboring.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. /new bilan qayta boshlang.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step", "title")
    text = (update.message.text or "").strip()

    if step == "title":
        context.user_data["title"] = text
        context.user_data["step"] = "body"
        await update.message.reply_text("Maqola matnini yuboring.")
        return

    if step == "body":
        context.user_data["body"] = text
        context.user_data["step"] = "desc"
        await update.message.reply_text("Qisqa description yuboring.")
        return

    if step == "desc":
        context.user_data["description"] = text
        context.user_data["step"] = "category"
        meta = fetch_meta()
        await update.message.reply_text(
            "Kategoriya tanlang:",
            reply_markup=build_category_keyboard(meta["categories"]),
        )
        return


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    context.user_data["photo_file_id"] = update.message.photo[-1].file_id
    await update.message.reply_text("Rasm qabul qilindi ✅")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data.startswith("cat:"):
        context.user_data["category_slug"] = data.split(":", 1)[1]
        context.user_data["step"] = "tags"
        meta = fetch_meta()
        context.user_data["all_tags"] = meta["tags"]
        context.user_data["selected_tags"] = []
        await query.edit_message_text(
            "Teglarni tanlang:",
            reply_markup=build_tag_keyboard(meta["tags"], []),
        )
        return

    if data.startswith("tag:"):
        value = data.split(":", 1)[1]
        selected = context.user_data.get("selected_tags", [])
        all_tags = context.user_data.get("all_tags", [])
        if value == "done":
            await query.edit_message_text("Post yuborilmoqda...")
            await create_post(update, context)
            return

        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        context.user_data["selected_tags"] = selected
        await query.edit_message_text(
            "Teglarni tanlang:",
            reply_markup=build_tag_keyboard(all_tags, selected),
        )


async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    file_id = data.get("photo_file_id")
    if not file_id:
        await update.effective_chat.send_message("Rasm yuborilmagan. Qaytadan /new.")
        return

    file = await context.bot.get_file(file_id)
    image_bytes = await file.download_as_bytearray()
    files = {"image": ("post.jpg", image_bytes)}
    payload = {
        "title": data.get("title", ""),
        "body": data.get("body", ""),
        "description": data.get("description", ""),
        "category_slug": data.get("category_slug", ""),
        "tag_slugs": ",".join(data.get("selected_tags", [])),
    }
    resp = requests.post(
        f"{API_BASE}/api/bot/post/",
        headers=api_headers(),
        data=payload,
        files=files,
        timeout=60,
    )
    result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not resp.ok or not result.get("ok"):
        await update.effective_chat.send_message(f"Xatolik: {resp.text}")
        return

    post_url = result.get("url", "")
    title = data.get("title", "")
    description = data.get("description", "")[:200]
    caption = f"🆕 {title}\n\n{description}\n\n{post_url}"

    if CHANNEL_ID:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=caption)

    context.user_data.clear()
    await update.effective_chat.send_message("Maqola saytga joylandi va kanalga yuborildi ✅")


def main():
    if not TG_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN is required.")
    if not API_BASE:
        raise RuntimeError("API_BASE is required.")

    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("new", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()


if __name__ == "__main__":
    main()
