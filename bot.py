import os
import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
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
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
DAILY_TIME = os.getenv("DAILY_TIME", "09:00")
DAILY_TZ = os.getenv("DAILY_TZ", "Asia/Tashkent")

STEPS = ["title", "body", "desc", "image", "category", "tags"]


def api_headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {BOT_API_TOKEN}"}


def fetch_meta() -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE}/api/bot/meta/", headers=api_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_recent_posts(limit: int = 10) -> Dict[str, Any]:
    resp = requests.get(
        f"{API_BASE}/api/bot/posts/",
        headers=api_headers(),
        params={"limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_daily_pick() -> Dict[str, Any]:
    resp = requests.get(
        f"{API_BASE}/api/bot/daily/next/",
        headers=api_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def mark_daily_pick(pick_id: int, action: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{API_BASE}/api/bot/daily/mark/",
        headers=api_headers(),
        data={"pick_id": pick_id, "action": action},
        timeout=30,
    )
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


def main_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🆕 Yangi maqola"), KeyboardButton("✅ Matn tugadi")],
            [KeyboardButton("📰 Oxirgi postlar"), KeyboardButton("📍 Holat")],
            [KeyboardButton("⬅️ Orqaga"), KeyboardButton("⏭️ Skip rasm"), KeyboardButton("❌ Bekor")],
        ],
        resize_keyboard=True,
    )


def step_name(step: str) -> str:
    names = {
        "title": "1/6 Sarlavha",
        "body": "2/6 Matn",
        "desc": "3/6 Description",
        "image": "4/6 Rasm",
        "category": "5/6 Kategoriya",
        "tags": "6/6 Teglar",
    }
    return names.get(step, step)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["step"] = "title"
    await update.message.reply_text("📝 Yangi maqola. Sarlavhani yuboring.", reply_markup=main_reply_keyboard())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step", "title")
    await update.message.reply_text(f"Joriy bosqich: {step_name(step)}", reply_markup=main_reply_keyboard())


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi. /new bilan qayta boshlang.", reply_markup=main_reply_keyboard())


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step", "title")
    idx = max(STEPS.index(step) - 1, 0)
    context.user_data["step"] = STEPS[idx]
    await update.message.reply_text(
        f"Orqaga qaytildi. Hozirgi bosqich: {step_name(context.user_data['step'])}",
        reply_markup=main_reply_keyboard(),
    )


async def skip_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")
    if step != "image":
        await update.message.reply_text("Bu bosqichda skip ishlamaydi.", reply_markup=main_reply_keyboard())
        return
    context.user_data["photo_file_id"] = None
    context.user_data["step"] = "category"
    try:
        meta = fetch_meta()
    except Exception as exc:
        await update.message.reply_text(f"❌ Kategoriya yuklanmadi: {exc}", reply_markup=main_reply_keyboard())
        return
    await update.message.reply_text(
        "Rasm o‘tkazildi. Kategoriya tanlang:",
        reply_markup=build_category_keyboard(meta["categories"]),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()

    if text == "🆕 Yangi maqola":
        await start(update, context)
        return
    if text == "📰 Oxirgi postlar":
        await show_recent_posts(update, context)
        return
    if text == "📍 Holat":
        await status(update, context)
        return
    if text == "⬅️ Orqaga":
        await back(update, context)
        return
    if text == "⏭️ Skip rasm":
        await skip_image(update, context)
        return
    if text == "❌ Bekor":
        await cancel(update, context)
        return
    if text == "✅ Matn tugadi":
        if not context.user_data.get("body"):
            await update.message.reply_text("Matn hali kiritilmagan.", reply_markup=main_reply_keyboard())
            return
        context.user_data["step"] = "desc"
        await update.message.reply_text("✅ Matn tugadi. Qisqa description yuboring.")
        return

    step = context.user_data.get("step", "title")

    if step == "title":
        context.user_data["title"] = text
        context.user_data["step"] = "body"
        await update.message.reply_text("✅ Sarlavha qabul qilindi. Endi matn yuboring.")
        return

    if step == "body":
        current = context.user_data.get("body", "")
        if current:
            current += "\n\n" + text
        else:
            current = text
        context.user_data["body"] = current
        await update.message.reply_text("✅ Qabul qilindi. Davom ettiring yoki 'Matn tugadi' bosing.")
        return

    if step == "desc":
        context.user_data["description"] = text
        context.user_data["step"] = "image"
        await update.message.reply_text("✅ Description qabul qilindi. Endi rasm yuboring (yoki 'Skip rasm').")
        return


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        return
    step = context.user_data.get("step")
    if step != "image":
        await update.message.reply_text("Rasm bosqichida emassiz. 'Holat' ni bosing.")
        return
    context.user_data["photo_file_id"] = update.message.photo[-1].file_id
    context.user_data["step"] = "category"
    try:
        meta = fetch_meta()
    except Exception as exc:
        await update.message.reply_text(f"❌ Kategoriya yuklanmadi: {exc}")
        return
    await update.message.reply_text(
        "✅ Rasm qabul qilindi. Kategoriya tanlang:",
        reply_markup=build_category_keyboard(meta["categories"]),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data.startswith("post:"):
        slug = data.split(":", 1)[1]
        post_lookup = context.user_data.get("recent_posts", {})
        post = post_lookup.get(slug)
        if not post:
            await query.edit_message_text("Post topilmadi. Qayta urinib ko'ring.")
            return
        await send_post_to_channel(update, post)
        return

    if data.startswith("daily:"):
        action, pick_id = data.split(":", 2)[1:]
        await handle_daily_decision(update, action, int(pick_id))
        return

    if data.startswith("cat:"):
        context.user_data["category_slug"] = data.split(":", 1)[1]
        context.user_data["step"] = "tags"
        try:
            meta = fetch_meta()
        except Exception as exc:
            await query.edit_message_text(f"❌ Teglar yuklanmadi: {exc}")
            return
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
            await query.edit_message_text("⏳ Post yuborilmoqda...")
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
    files = {}
    file_id = data.get("photo_file_id")
    if file_id:
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
    try:
        resp = requests.post(
            f"{API_BASE}/api/bot/post/",
            headers=api_headers(),
            data=payload,
            files=files,
            timeout=60,
        )
    except Exception as exc:
        await update.effective_chat.send_message(f"❌ APIga ulanishda xato: {exc}")
        return
    result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not resp.ok or not result.get("ok"):
        err_text = resp.text
        if len(err_text) > 1000:
            err_text = err_text[:1000] + "..."
        await update.effective_chat.send_message(f"❌ API xato: {err_text}")
        return

    post_url = result.get("url", "")
    title = data.get("title", "")
    description = (data.get("description", "") or "").strip()
    body_text = (data.get("body", "") or "").strip()
    preview_source = description if description else body_text
    preview = preview_source[:400]
    caption = f"🆕 {title}\n\n{preview}\n\n{post_url}"

    if CHANNEL_ID:
        if file_id:
            await context.bot.send_photo(chat_id=CHANNEL_ID, photo=file_id, caption=caption)
        else:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)

    context.user_data.clear()
    await update.effective_chat.send_message("✅ Maqola saytga joylandi va kanalga yuborildi.", reply_markup=main_reply_keyboard())


async def show_recent_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        payload = fetch_recent_posts(limit=10)
    except Exception as exc:
        await update.message.reply_text(f"❌ Postlar yuklanmadi: {exc}", reply_markup=main_reply_keyboard())
        return
    posts = payload.get("posts", [])
    if not posts:
        await update.message.reply_text("Postlar topilmadi.", reply_markup=main_reply_keyboard())
        return
    context.user_data["recent_posts"] = {p["slug"]: p for p in posts}
    buttons = [[InlineKeyboardButton(p["title"], callback_data=f"post:{p['slug']}")] for p in posts]
    await update.message.reply_text("Kanalga yuborish uchun postni tanlang:", reply_markup=InlineKeyboardMarkup(buttons))


async def send_post_to_channel(update: Update, post: Dict[str, Any]):
    if not CHANNEL_ID:
        await update.effective_chat.send_message("❌ TELEGRAM_CHANNEL_ID sozlanmagan.")
        return
    title = post.get("title", "")
    url = post.get("url", "")
    excerpt = (post.get("excerpt", "") or "").strip()
    preview = excerpt[:400] if excerpt else ""
    caption = f"🆕 {title}\n\n{preview}\n\n{url}"
    await update.effective_chat.send_message("⏳ Kanalga yuborilmoqda...")
    await update.effective_chat.bot.send_message(chat_id=CHANNEL_ID, text=caption)
    await update.effective_chat.send_message("✅ Kanalga yuborildi.", reply_markup=main_reply_keyboard())


async def send_daily_pick_to_admin(context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_CHAT_ID:
        return
    try:
        payload = fetch_daily_pick()
    except Exception as exc:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Daily pick xato: {exc}")
        return
    if not payload.get("ok"):
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Daily pick xato: {payload}")
        return
    pick_id = payload.get("pick_id")
    post = payload.get("post", {})
    title = post.get("title", "")
    url = post.get("url", "")
    excerpt = (post.get("excerpt", "") or "").strip()
    preview = excerpt[:400]
    caption = f"🆕 {title}\n\n{preview}\n\n{url}"
    buttons = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"daily:sent:{pick_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"daily:rejected:{pick_id}"),
        ]
    ]
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=caption,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_daily_decision(update: Update, action: str, pick_id: int):
    if action not in ("sent", "rejected"):
        await update.effective_chat.send_message("❌ Noto‘g‘ri qaror.")
        return
    try:
        mark_daily_pick(pick_id, action)
    except Exception as exc:
        await update.effective_chat.send_message(f"❌ Mark xato: {exc}")
        return
    if action == "sent":
        await update.effective_chat.send_message("⏳ Kanalga yuborilmoqda...")
        post_payload = fetch_daily_pick()
        post = post_payload.get("post", {})
        await send_post_to_channel(update, post)
    else:
        await update.effective_chat.send_message("❌ Post rad etildi.", reply_markup=main_reply_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    msg = f"❌ Bot xatosi: {type(err).__name__}: {err}"
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    try:
        if update and hasattr(update, "effective_chat") and update.effective_chat:
            await update.effective_chat.send_message(msg)
    except Exception:
        pass


def main():
    if not TG_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN is required.")
    if not API_BASE:
        raise RuntimeError("API_BASE is required.")

    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("new", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("back", back))
    app.add_handler(CommandHandler("skip", skip_image))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)
    try:
        hour, minute = DAILY_TIME.split(":")
        daily_time = datetime.time(int(hour), int(minute))
        tz = ZoneInfo(DAILY_TZ)
        app.job_queue.run_daily(send_daily_pick_to_admin, time=daily_time, timezone=tz)
    except Exception:
        pass
    app.run_polling()


if __name__ == "__main__":
    main()
