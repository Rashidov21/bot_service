import os
import json
import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any, List

import requests
from dotenv import load_dotenv
import markdown as md
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
AI_POST_TIMES = os.getenv("AI_POST_TIMES", "09:00,15:00").split(",")
AI_POST_INSTRUCTIONS = os.getenv(
    "AI_POST_INSTRUCTIONS",
    "Python, dasturlash, veb dasturlash, Django, JavaScript haqida yozing. O'zbek tilida, qiziqarli va foydali maqolalar."
)

STEPS = ["title", "body", "desc", "image", "category", "tags"]


def api_headers() -> Dict[str, str]:
    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN is not set in environment variables!")
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


# AI Topics ro'yxati
AI_TOPICS = [
    "Python'da decoratorlar",
    "Django ORM optimizatsiyasi",
    "JavaScript async/await",
    "React hooks",
    "SQL query optimizatsiyasi",
    "Python list comprehension",
    "Django middleware",
    "JavaScript closures",
    "Python generators",
    "Django REST framework",
    "JavaScript promises",
    "Python context managers",
    "Django signals",
    "JavaScript ES6 features",
    "Python virtual environments",
]

# AI Settings file
AI_SETTINGS_FILE = "ai_settings.json"


def load_ai_settings():
    """AI sozlamalarini yuklash"""
    default_settings = {
        "instructions": AI_POST_INSTRUCTIONS,
        "trends": [],
        "topics": AI_TOPICS.copy(),
    }
    try:
        if os.path.exists(AI_SETTINGS_FILE):
            with open(AI_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Default qiymatlar bilan birlashtirish
                default_settings.update(data)
        return default_settings
    except Exception:
        return default_settings


def save_ai_settings(settings):
    """AI sozlamalarini saqlash"""
    try:
        with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_ai_settings():
    """Hozirgi sozlamalarni olish"""
    return load_ai_settings()


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

    # AI mavzu kiritish rejimi
    if context.user_data.get("ai_mode") == "await_topic":
        context.user_data["ai_mode"] = None
        await update.message.reply_text("⏳ AI draft generatsiya qilmoqda...")
        try:
            resp = requests.post(
                f"{API_BASE}/api/bot/ai/post-idea/",
                headers=api_headers(),
                data={"topic": text},
                timeout=120,
            )
            data = resp.json()
            if not resp.ok or not data.get("ok"):
                raise Exception(data.get("error") or resp.text)
            idea = data["data"]
            
            # Uzun javoblarni bo'laklarga bo'lish
            header_msg = (
                f"🧠 AI g'oya:\n\n"
                f"📌 *Sarlavha:* {idea['title']}\n\n"
                f"📝 *Description:*\n{idea['description']}\n\n"
            )
            await update.message.reply_text(header_msg, parse_mode="Markdown")
            
            # Body alohida xabarda (agar uzun bo'lsa, bo'laklarga bo'lish)
            body = idea['body_markdown']
            footer_text = "\n\nAgar yoqsa, /new bosib, AI bergan sarlavha/description/body'ni copy-paste qilib yuklashingiz mumkin."
            
            if len(body) > 3500:
                # Body juda uzun bo'lsa, bo'laklarga bo'lish
                chunks = [body[i:i+3500] for i in range(0, len(body), 3500)]
                for idx, chunk in enumerate(chunks):
                    prefix = f"📄 *Draft (qism {idx+1}/{len(chunks)}):*\n\n" if len(chunks) > 1 else "📄 *Draft:*\n\n"
                    suffix = footer_text if idx == len(chunks) - 1 else ""
                    await update.message.reply_text(f"{prefix}{chunk}{suffix}", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"📄 *Draft:*\n\n{body}{footer_text}", parse_mode="Markdown")
                
        except Exception as exc:
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ AI xato: {exc}")
            await update.message.reply_text("❌ AI draft yaratishda xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return

    # Manual AI Draft mavzu kiritish rejimi
    if context.user_data.get("ai_draft_mode") == "await_topic":
        context.user_data["ai_draft_mode"] = None
        context.user_data["ai_draft_manual"] = None
        await update.message.reply_text("⏳ AI draft generatsiya qilmoqda... Bu biroz vaqt olishi mumkin.")
        
        try:
            settings = get_ai_settings()
            instructions = settings.get('instructions', AI_POST_INSTRUCTIONS)
            trends = settings.get('trends', [])
            if trends:
                trends_text = "\n\nHozirgi trendlar:\n" + "\n".join(f"- {t}" for t in trends)
                instructions = instructions + trends_text
            
            resp = requests.post(
                f"{API_BASE}/api/bot/ai/draft/create/",
                headers=api_headers(),
                data={
                    "topic": text,
                    "instructions": instructions,
                },
                timeout=180,
            )
            
            # Response status code tekshirish
            if not resp.ok:
                error_text = resp.text[:500] if resp.text else "Unknown error"
                raise Exception(f"API error ({resp.status_code}): {error_text}")
            
            # JSON parsing xatolarini handle qilish
            try:
                data = resp.json()
            except ValueError as json_err:
                error_text = resp.text[:500] if resp.text else "Empty response"
                raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
            
            if not data.get("ok"):
                error_msg = data.get("error", "Unknown error")
                raise Exception(error_msg)
            
            draft_id = data.get("draft_id")
            title = data.get("title")
            description = data.get("description")
            body_preview = data.get("body_markdown", "")[:300]
            
            if not draft_id or not title:
                raise Exception("API response missing required fields")
            
            msg = (
                f"🤖 *AI yangi draft yaratdi:*\n\n"
                f"📌 *Mavzu:* {text}\n\n"
                f"📝 *Sarlavha:* {title}\n\n"
                f"📄 *Description:*\n{description}\n\n"
                f"📖 *Body (preview):*\n{body_preview}...\n\n"
                f"`Draft ID: {draft_id}`"
            )
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"aidraft:approve:{draft_id}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"aidraft:reject:{draft_id}"),
                ],
                [
                    InlineKeyboardButton("🔄 Qayta generatsiya", callback_data=f"aidraft:regenerate:{draft_id}"),
                ],
            ]
            
            await update.message.reply_text(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except requests.exceptions.RequestException as exc:
            error_msg = str(exc)
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."
            await update.message.reply_text(f"❌ Tarmoq xatosi: {error_msg}")
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ AI draft network error: {exc}")
        except Exception as exc:
            error_msg = str(exc)
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."
            await update.message.reply_text(f"❌ AI draft xato: {error_msg}")
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ AI draft error: {exc}")
        return

    # AI Settings mode
    if context.user_data.get("ai_settings_mode") == "edit_instructions":
        context.user_data["ai_settings_mode"] = None
        settings = get_ai_settings()
        settings['instructions'] = text
        if save_ai_settings(settings):
            await update.message.reply_text("✅ Sozlama yangilandi!")
        else:
            await update.message.reply_text("❌ Xatolik: Sozlama saqlanmadi.")
        return
    
    if context.user_data.get("ai_settings_mode") == "add_trend":
        context.user_data["ai_settings_mode"] = None
        settings = get_ai_settings()
        if 'trends' not in settings:
            settings['trends'] = []
        settings['trends'].append(text)
        if save_ai_settings(settings):
            await update.message.reply_text(f"✅ Trend qo'shildi: {text}")
        else:
            await update.message.reply_text("❌ Xatolik: Trend saqlanmadi.")
        return
    
    if context.user_data.get("ai_settings_mode") == "add_topic":
        context.user_data["ai_settings_mode"] = None
        settings = get_ai_settings()
        if 'topics' not in settings:
            settings['topics'] = []
        settings['topics'].append(text)
        if save_ai_settings(settings):
            await update.message.reply_text(f"✅ Mavzu qo'shildi: {text}")
        else:
            await update.message.reply_text("❌ Xatolik: Mavzu saqlanmadi.")
        return
    
    # AI Trend mode (ai_trends_command dan)
    if context.user_data.get("ai_trend_mode") == "add":
        context.user_data["ai_trend_mode"] = None
        settings = get_ai_settings()
        if 'trends' not in settings:
            settings['trends'] = []
        settings['trends'].append(text)
        if save_ai_settings(settings):
            await update.message.reply_text(f"✅ Trend qo'shildi: {text}")
        else:
            await update.message.reply_text("❌ Xatolik: Trend saqlanmadi.")
        return

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
        # AI Draft uchun skip
        if context.user_data.get("ai_draft_step") == "image":
            context.user_data["ai_draft_photo_file_id"] = None
            await finalize_ai_draft_post(update, context)
            return
        # Oddiy post uchun skip
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
    
    # AI Draft image
    if context.user_data.get("ai_draft_step") == "image":
        context.user_data["ai_draft_photo_file_id"] = update.message.photo[-1].file_id
        await finalize_ai_draft_post(update, context)
        return
    
    # Oddiy post image
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

    if data.startswith("postid:"):
        post_id = data.split(":", 1)[1]
        post_lookup = context.user_data.get("recent_posts", {})
        post = post_lookup.get(post_id)
        if not post:
            await query.edit_message_text("Post topilmadi. Qayta urinib ko'ring.")
            return
        await send_post_to_channel(update, context, post)
        return

    if data.startswith("daily:"):
        action, pick_id = data.split(":", 2)[1:]
        await handle_daily_decision(update, context, action, int(pick_id))
        return

    # AI Draft callbacks
    if data.startswith("aidraft:"):
        action, draft_id = data.split(":", 2)[1:]
        await handle_ai_draft_decision(update, context, action, int(draft_id))
        return

    # AI Settings callbacks
    if data.startswith("aisettings:"):
        action = data.split(":", 1)[1]
        await handle_ai_settings_callback(update, context, action)
        return
    
    # AI Trends callbacks
    if data.startswith("aitrend:"):
        action = data.split(":", 1)[1]
        await handle_ai_trends_callback(update, context, action)
        return

    # Category tanlash - AI Draft yoki oddiy post uchun
    if data.startswith("cat:"):
        if context.user_data.get("ai_draft_step") == "category":
            # AI Draft uchun
            category_slug = data.split(":", 1)[1]
            context.user_data["ai_draft_category_slug"] = category_slug
            context.user_data["ai_draft_step"] = "tags"
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
        else:
            # Oddiy post uchun
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

    # Tag tanlash - AI Draft yoki oddiy post uchun
    if data.startswith("tag:"):
        value = data.split(":", 1)[1]
        selected = context.user_data.get("selected_tags", [])
        all_tags = context.user_data.get("all_tags", [])
        
        if value == "done":
            if context.user_data.get("ai_draft_step") == "tags":
                # AI Draft uchun - rasm so'rash
                context.user_data["ai_draft_step"] = "image"
                await query.edit_message_text("Endi rasm yuboring (yoki 'Skip rasm' tugmasini bosing):")
            else:
                # Oddiy post uchun
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
    body_text = (data.get("body", "") or "").strip()
    body_html = md.markdown(body_text, extensions=["fenced_code", "tables"])
    payload = {
        "title": data.get("title", ""),
        "body": body_text,
        "body_text": body_text,
        "body_html": body_html,
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
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ APIga ulanishda xato: {exc}")
        # Foydalanuvchiga umumiy xabar
        await update.effective_chat.send_message("❌ Maqola yuborishda xatolik yuz berdi. Admin bilan bog'lanish.")
        return
    result = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if not resp.ok or not result.get("ok"):
        err_text = resp.text
        if len(err_text) > 1000:
            err_text = err_text[:1000] + "..."
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ API xato: {err_text}")
        # Foydalanuvchiga umumiy xabar
        await update.effective_chat.send_message("❌ Maqola yuborishda xatolik yuz berdi. Admin bilan bog'lanish.")
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
    context.user_data["recent_posts"] = {str(p["id"]): p for p in posts}
    buttons = [[InlineKeyboardButton(p["title"], callback_data=f"postid:{p['id']}")] for p in posts]
    await update.message.reply_text("Kanalga yuborish uchun postni tanlang:", reply_markup=InlineKeyboardMarkup(buttons))


async def send_post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, post: Dict[str, Any]):
    if not CHANNEL_ID:
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="❌ TELEGRAM_CHANNEL_ID sozlanmagan.")
        await update.effective_chat.send_message("❌ Kanal sozlanmagan. Admin bilan bog'lanish.")
        return
    title = post.get("title", "")
    url = post.get("url", "")
    excerpt = (post.get("excerpt", "") or "").strip()
    preview = excerpt[:400] if excerpt else ""
    caption = f"🆕 {title}\n\n{preview}\n\n{url}"
    await update.effective_chat.send_message("⏳ Kanalga yuborilmoqda...")
    try:
        # Faqat maqolani kanalga yuborish
        await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        await update.effective_chat.send_message("✅ Kanalga yuborildi.", reply_markup=main_reply_keyboard())
    except Exception as exc:
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Kanalga yuborishda xato: {exc}")
        await update.effective_chat.send_message("❌ Kanalga yuborishda xatolik yuz berdi. Admin bilan bog'lanish.")


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


async def handle_daily_decision(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, pick_id: int):
    if action not in ("sent", "rejected"):
        await update.effective_chat.send_message("❌ Noto'g'ri qaror.")
        return
    
    # "sent" bo'lsa, avval post ma'lumotlarini olish (mark_daily_pick chaqirilishidan oldin)
    post = None
    if action == "sent":
        try:
            # Post ma'lumotlarini API dan olish (mark_daily_pick chaqirilishidan oldin)
            post_payload = fetch_daily_pick()
            if post_payload.get("ok") and post_payload.get("pick_id") == pick_id:
                post = post_payload.get("post", {})
        except Exception as exc:
            # Xatolikni faqat admin ga yuborish
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Post ma'lumotlarini olishda xato: {exc}")
    
    # Endi mark_daily_pick ni chaqirish
    try:
        mark_daily_pick(pick_id, action)
    except Exception as exc:
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Mark xato: {exc}")
        await update.effective_chat.send_message("❌ Xatolik yuz berdi. Admin bilan bog'lanish.")
        return
    
    if action == "sent":
        if not post:
            # Agar post ma'lumotlari olinmagan bo'lsa, xatolik yuborish
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Post ma'lumotlari olinmadi (pick_id: {pick_id})")
            await update.effective_chat.send_message("❌ Kanalga yuborishda xatolik yuz berdi. Admin bilan bog'lanish.")
            return
        
        await update.effective_chat.send_message("⏳ Kanalga yuborilmoqda...")
        try:
            # Faqat maqolani kanalga yuborish
            await send_post_to_channel(update, context, post)
        except Exception as exc:
            # Xatolikni faqat admin ga yuborish
            if ADMIN_CHAT_ID:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"❌ Daily pick kanalga yuborishda xato: {exc}")
            await update.effective_chat.send_message("❌ Kanalga yuborishda xatolik yuz berdi. Admin bilan bog'lanish.")
    else:
        await update.effective_chat.send_message("❌ Post rad etildi.", reply_markup=main_reply_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    msg = f"❌ Bot xatosi: {type(err).__name__}: {err}"
    if len(msg) > 1000:
        msg = msg[:1000] + "..."
    try:
        # Xatolikni faqat admin ga yuborish
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)
        # Foydalanuvchiga umumiy xabar (agar update mavjud bo'lsa va kanal emas bo'lsa)
        if update and hasattr(update, "effective_chat") and update.effective_chat:
            chat_id = update.effective_chat.id
            # Kanal ID negativ bo'ladi, shuning uchun tekshiramiz
            if CHANNEL_ID and str(chat_id) != str(CHANNEL_ID):
                try:
                    await update.effective_chat.send_message("❌ Bot xatosi yuz berdi. Admin bilan bog'lanish.")
                except Exception:
                    pass
    except Exception:
        pass


async def ai_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("AI yordamida maqola yozish uchun mavzuni yuboring:")
    context.user_data["ai_mode"] = "await_topic"


async def ai_draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual AI draft yaratish"""
    if not ADMIN_CHAT_ID or str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("❌ Bu funksiya faqat admin uchun.")
        return
    
    await update.message.reply_text(
        "🤖 AI draft yaratish uchun mavzuni yuboring:\n\n"
        "Masalan: 'Python decoratorlar haqida', 'Django ORM optimizatsiyasi', va hokazo."
    )
    context.user_data["ai_draft_manual"] = True
    context.user_data["ai_draft_mode"] = "await_topic"


async def ai_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI sozlamalarini ko'rish va o'zgartirish"""
    if not ADMIN_CHAT_ID or str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("❌ Bu funksiya faqat admin uchun.")
        return
    
    settings = get_ai_settings()
    
    msg = (
        f"🤖 *AI Sozlamalar:*\n\n"
        f"📝 *Hozirgi sozlama:*\n{settings['instructions']}\n\n"
        f"📊 *Trendlar ({len(settings.get('trends', []))}):*\n"
    )
    
    trends = settings.get('trends', [])
    if trends:
        for i, trend in enumerate(trends[:5], 1):  # Faqat birinchi 5 tasini ko'rsatish
            msg += f"{i}. {trend}\n"
        if len(trends) > 5:
            msg += f"... va yana {len(trends) - 5} ta\n"
    else:
        msg += "Trendlar yo'q\n"
    
    msg += f"\n📌 *Mavzular ({len(settings.get('topics', []))}):*\n"
    topics = settings.get('topics', [])
    if topics:
        for i, topic in enumerate(topics[:5], 1):
            msg += f"{i}. {topic}\n"
        if len(topics) > 5:
            msg += f"... va yana {len(topics) - 5} ta\n"
    
    buttons = [
        [InlineKeyboardButton("✏️ Sozlama o'zgartirish", callback_data="aisettings:edit_instructions")],
        [InlineKeyboardButton("📊 Trend qo'shish", callback_data="aisettings:add_trend")],
        [InlineKeyboardButton("📊 Trendlar ro'yxati", callback_data="aisettings:list_trends")],
        [InlineKeyboardButton("📌 Mavzu qo'shish", callback_data="aisettings:add_topic")],
        [InlineKeyboardButton("📌 Mavzular ro'yxati", callback_data="aisettings:list_topics")],
    ]
    
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def ai_trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trendlarni boshqarish"""
    if not ADMIN_CHAT_ID or str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("❌ Bu funksiya faqat admin uchun.")
        return
    
    settings = get_ai_settings()
    trends = settings.get('trends', [])
    
    if not trends:
        await update.message.reply_text(
            "📊 Hozircha trendlar yo'q.\n\n"
            "Trend qo'shish uchun matn yuboring:"
        )
        context.user_data["ai_trend_mode"] = "add"
        return
    
    msg = f"📊 *Trendlar ({len(trends)}):*\n\n"
    for i, trend in enumerate(trends, 1):
        msg += f"{i}. {trend}\n"
    
    buttons = [
        [InlineKeyboardButton("➕ Yangi trend", callback_data="aitrend:add")],
        [InlineKeyboardButton("🗑️ Trend o'chirish", callback_data="aitrend:delete")],
    ]
    
    await update.message.reply_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def generate_ai_draft(context: ContextTypes.DEFAULT_TYPE):
    """AI'dan draft generatsiya qilish (rejalashtirilgan)"""
    if not ADMIN_CHAT_ID:
        return
    
    import random
    settings = get_ai_settings()
    topics = settings.get('topics', AI_TOPICS)
    topic = random.choice(topics)
    
    # Trendlarni instructions ga qo'shish
    instructions = settings.get('instructions', AI_POST_INSTRUCTIONS)
    trends = settings.get('trends', [])
    if trends:
        trends_text = "\n\nHozirgi trendlar:\n" + "\n".join(f"- {t}" for t in trends)
        instructions = instructions + trends_text
    
    try:
        resp = requests.post(
            f"{API_BASE}/api/bot/ai/draft/create/",
            headers=api_headers(),
            data={
                "topic": topic,
                "instructions": instructions,
            },
            timeout=180,
        )
        
        # Response status code tekshirish
        if not resp.ok:
            error_text = resp.text[:500] if resp.text else "Unknown error"
            raise Exception(f"API error ({resp.status_code}): {error_text}")
        
        # JSON parsing xatolarini handle qilish
        try:
            data = resp.json()
        except ValueError as json_err:
            error_text = resp.text[:500] if resp.text else "Empty response"
            raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
        
        if not data.get("ok"):
            raise Exception(data.get("error") or resp.text)
        
        draft_id = data.get("draft_id")
        title = data.get("title")
        description = data.get("description")
        body_preview = data.get("body_markdown", "")[:300]
        
        if not draft_id or not title:
            raise Exception("API response missing required fields")
        
        # Admin'ga yuborish
        msg = (
            f"🤖 AI yangi draft yaratdi:\n\n"
            f"📌 *Mavzu:* {topic}\n\n"
            f"📝 *Sarlavha:* {title}\n\n"
            f"📄 *Description:*\n{description}\n\n"
            f"📖 *Body (preview):*\n{body_preview}...\n\n"
            f"Draft ID: {draft_id}"
        )
        
        buttons = [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"aidraft:approve:{draft_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"aidraft:reject:{draft_id}"),
            ],
            [
                InlineKeyboardButton("🔄 Qayta generatsiya", callback_data=f"aidraft:regenerate:{draft_id}"),
            ],
        ]
        
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        
    except requests.exceptions.RequestException as exc:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ AI draft network error: {exc}"
            )
    except Exception as exc:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"❌ AI draft generatsiya xato: {exc}"
            )


async def handle_ai_draft_decision(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, draft_id: int):
    """AI Draft tasdiqlash/rad etish/qayta generatsiya"""
    
    if action == "approve":
        # Draftni olish va kategoriya tanlash uchun yuborish
        try:
            resp = requests.get(
                f"{API_BASE}/api/bot/ai/draft/get/",
                headers=api_headers(),
                params={"draft_id": draft_id},
                timeout=30,
            )
            
            if not resp.ok:
                error_text = resp.text[:500] if resp.text else "Unknown error"
                raise Exception(f"API error ({resp.status_code}): {error_text}")
            
            try:
                data = resp.json()
            except ValueError as json_err:
                error_text = resp.text[:500] if resp.text else "Empty response"
                raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
            
            if not data.get("ok"):
                raise Exception(data.get("error") or resp.text)
            
            # Meta olish (categories, tags)
            meta = fetch_meta()
            
            # Kategoriya tanlash uchun yuborish
            await update.effective_chat.send_message(
                "✅ Draft tasdiqlandi. Endi kategoriya tanlang:",
                reply_markup=build_category_keyboard(meta["categories"]),
            )
            
            # Context'ga saqlash
            context.user_data["ai_draft_id"] = draft_id
            context.user_data["ai_draft_step"] = "category"
            
        except Exception as exc:
            error_msg = str(exc)
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."
            await update.effective_chat.send_message(f"❌ Xato: {error_msg}")
    
    elif action == "reject":
        try:
            resp = requests.post(
                f"{API_BASE}/api/bot/ai/draft/reject/",
                headers=api_headers(),
                data={"draft_id": draft_id},
                timeout=30,
            )
            
            if not resp.ok:
                error_text = resp.text[:500] if resp.text else "Unknown error"
                raise Exception(f"API error ({resp.status_code}): {error_text}")
            
            try:
                data = resp.json()
            except ValueError as json_err:
                error_text = resp.text[:500] if resp.text else "Empty response"
                raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
            
            if data.get("ok"):
                await update.effective_chat.send_message("❌ Draft rad etildi.")
            else:
                await update.effective_chat.send_message(f"❌ Xato: {data.get('error', 'Unknown error')}")
        except Exception as exc:
            error_msg = str(exc)
            if len(error_msg) > 1000:
                error_msg = error_msg[:1000] + "..."
            await update.effective_chat.send_message(f"❌ Xato: {error_msg}")
    
    elif action == "regenerate":
        await update.effective_chat.send_message("🔄 Qayta generatsiya qilinmoqda...")
        try:
            resp = requests.post(
                f"{API_BASE}/api/bot/ai/draft/regenerate/",
                headers=api_headers(),
                data={"draft_id": draft_id},
                timeout=180,
            )
            
            if not resp.ok:
                error_text = resp.text[:500] if resp.text else "Unknown error"
                raise Exception(f"API error ({resp.status_code}): {error_text}")
            
            try:
                data = resp.json()
            except ValueError as json_err:
                error_text = resp.text[:500] if resp.text else "Empty response"
                raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
            
            if not data.get("ok"):
                raise Exception(data.get("error") or resp.text)
            
            # Yangi draftni admin'ga yuborish
            title = data.get("title")
            description = data.get("description")
            body_preview = data.get("body_markdown", "")[:300]
            
            msg = (
                f"🔄 Yangi draft:\n\n"
                f"📝 *Sarlavha:* {title}\n\n"
                f"📄 *Description:*\n{description}\n\n"
                f"📖 *Body (preview):*\n{body_preview}...\n\n"
                f"Draft ID: {draft_id}"
            )
            
            buttons = [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"aidraft:approve:{draft_id}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"aidraft:reject:{draft_id}"),
                ],
                [
                    InlineKeyboardButton("🔄 Qayta generatsiya", callback_data=f"aidraft:regenerate:{draft_id}"),
                ],
            ]
            
            await update.effective_chat.send_message(
                msg,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as exc:
            await update.effective_chat.send_message(f"❌ Xato: {exc}")


async def handle_ai_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """AI Settings callback handler"""
    
    if action == "edit_instructions":
        await update.callback_query.answer()
        await update.effective_chat.send_message(
            "✏️ Yangi sozlama matnini yuboring:\n\n"
            "Masalan: 'Python, dasturlash, veb dasturlash haqida yozing. O'zbek tilida, qiziqarli va foydali maqolalar.'"
        )
        context.user_data["ai_settings_mode"] = "edit_instructions"
    
    elif action == "add_trend":
        await update.callback_query.answer()
        await update.effective_chat.send_message("📊 Yangi trend matnini yuboring:")
        context.user_data["ai_settings_mode"] = "add_trend"
    
    elif action == "list_trends":
        await update.callback_query.answer()
        settings = get_ai_settings()
        trends = settings.get('trends', [])
        if not trends:
            await update.effective_chat.send_message("📊 Trendlar yo'q.")
        else:
            msg = f"📊 *Trendlar ({len(trends)}):*\n\n"
            for i, trend in enumerate(trends, 1):
                msg += f"{i}. {trend}\n"
            await update.effective_chat.send_message(msg, parse_mode="Markdown")
    
    elif action == "add_topic":
        await update.callback_query.answer()
        await update.effective_chat.send_message("📌 Yangi mavzu nomini yuboring:")
        context.user_data["ai_settings_mode"] = "add_topic"
    
    elif action == "list_topics":
        await update.callback_query.answer()
        settings = get_ai_settings()
        topics = settings.get('topics', [])
        if not topics:
            await update.effective_chat.send_message("📌 Mavzular yo'q.")
        else:
            msg = f"📌 *Mavzular ({len(topics)}):*\n\n"
            for i, topic in enumerate(topics, 1):
                msg += f"{i}. {topic}\n"
            await update.effective_chat.send_message(msg, parse_mode="Markdown")


async def handle_ai_trends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """AI Trends callback handler"""
    
    if action == "add":
        await update.callback_query.answer()
        await update.effective_chat.send_message("📊 Yangi trend matnini yuboring:")
        context.user_data["ai_trend_mode"] = "add"
    
    elif action == "delete":
        await update.callback_query.answer()
        settings = get_ai_settings()
        trends = settings.get('trends', [])
        if not trends:
            await update.effective_chat.send_message("📊 O'chirish uchun trendlar yo'q.")
            return
        
        # Inline keyboard bilan trend tanlash
        buttons = []
        for i, trend in enumerate(trends):
            buttons.append([
                InlineKeyboardButton(
                    f"🗑️ {trend[:30]}...",
                    callback_data=f"aitrend:del:{i}"
                )
            ])
        buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="aitrend:cancel")])
        
        await update.effective_chat.send_message(
            "🗑️ O'chirish uchun trendni tanlang:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    
    elif action.startswith("del:"):
        await update.callback_query.answer()
        idx = int(action.split(":")[1])
        settings = get_ai_settings()
        trends = settings.get('trends', [])
        if 0 <= idx < len(trends):
            deleted = trends.pop(idx)
            settings['trends'] = trends
            if save_ai_settings(settings):
                await update.effective_chat.send_message(f"✅ Trend o'chirildi: {deleted}")
            else:
                await update.effective_chat.send_message("❌ Xatolik: Sozlamalar saqlanmadi.")
        else:
            await update.effective_chat.send_message("❌ Noto'g'ri indeks.")
    
    elif action == "cancel":
        await update.callback_query.answer("Bekor qilindi")


async def finalize_ai_draft_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI Draftni post qilib yaratish"""
    draft_id = context.user_data.get("ai_draft_id")
    category_slug = context.user_data.get("ai_draft_category_slug")
    selected_tags = context.user_data.get("selected_tags", [])
    photo_file_id = context.user_data.get("ai_draft_photo_file_id", "")
    
    if not draft_id or not category_slug:
        await update.message.reply_text("❌ Ma'lumotlar to'liq emas.")
        return
    
    # Category ID olish
    meta = fetch_meta()
    category = next((c for c in meta["categories"] if c["slug"] == category_slug), None)
    if not category:
        await update.message.reply_text("❌ Kategoriya topilmadi.")
        return
    
    # Tag IDs
    tag_ids = ",".join(selected_tags) if selected_tags else ""
    
    # Post yaratish
    await update.message.reply_text("⏳ Post yaratilmoqda...")
    
    try:
        resp = requests.post(
            f"{API_BASE}/api/bot/ai/draft/approve/",
            headers=api_headers(),
            data={
                "draft_id": draft_id,
                "category_id": category["id"],
                "tag_ids": tag_ids,
                "image_file_id": photo_file_id or "",
            },
            timeout=60,
        )
        
        if not resp.ok:
            error_text = resp.text[:500] if resp.text else "Unknown error"
            raise Exception(f"API error ({resp.status_code}): {error_text}")
        
        try:
            data = resp.json()
        except ValueError as json_err:
            error_text = resp.text[:500] if resp.text else "Empty response"
            raise Exception(f"JSON parsing error: {json_err}. Response: {error_text}")
        
        if not data.get("ok"):
            raise Exception(data.get("error") or resp.text)
        
        post_url = data.get("url")
        post_title = data.get("title")
        
        # Kanalga yuborish
        if CHANNEL_ID:
            caption = f"🆕 {post_title}\n\n{post_url}"
            if photo_file_id:
                await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo_file_id, caption=caption)
            else:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=caption)
        
        # Context tozalash
        context.user_data.pop("ai_draft_id", None)
        context.user_data.pop("ai_draft_step", None)
        context.user_data.pop("ai_draft_category_slug", None)
        context.user_data.pop("selected_tags", None)
        context.user_data.pop("ai_draft_photo_file_id", None)
        context.user_data.pop("all_tags", None)
        
        await update.message.reply_text(
            f"✅ Post saytga joylandi va kanalga yuborildi!\n\n{post_url}",
            reply_markup=main_reply_keyboard(),
        )
        
    except Exception as exc:
        await update.message.reply_text(f"❌ Xato: {exc}")


def main():
    if not TG_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not BOT_API_TOKEN:
        raise RuntimeError("BOT_API_TOKEN is required.")
    if not API_BASE:
        raise RuntimeError("API_BASE is required.")

    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("new", start))
    app.add_handler(CommandHandler("ai_post", ai_post_command))
    app.add_handler(CommandHandler("ai_draft", ai_draft_command))
    app.add_handler(CommandHandler("ai_settings", ai_settings_command))
    app.add_handler(CommandHandler("ai_trends", ai_trends_command))
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
    
    # Kunda 2 marta AI draft generatsiya
    for time_str in AI_POST_TIMES:
        try:
            hour, minute = time_str.strip().split(":")
            daily_time = datetime.time(int(hour), int(minute))
            tz = ZoneInfo(DAILY_TZ)
            app.job_queue.run_daily(generate_ai_draft, time=daily_time, timezone=tz)
        except Exception:
            pass
    
    app.run_polling()


if __name__ == "__main__":
    main()
