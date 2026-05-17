"""
Telegram-бот с ИИ-ответами и генерацией картинок через KIE AI
Зависимости: pip install python-telegram-bot httpx
"""

import csv
import logging
import os
import httpx
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# ─── Настройки ───────────────────────────────────────────────────────────────
BOT_TOKEN = "8610613129:AAGtDbgtyxigBi3E_BaRb7R6DpI-HQvh3cc"       # токен от @BotFather
ADMIN_CHAT_ID = 1150947024            
KIE_API_KEY = "9e38c0f07f3dcb598db06531b7cc451e"    # ключ от kie.ai
CSV_FILE = "orders.csv"

SYSTEM_PROMPT = """Ты умный помощник в Telegram-боте.
Отвечай кратко, дружелюбно и по делу на русском языке.
Помогаешь клиентам с вопросами и принимаешь заявки.
Если клиент хочет оставить заявку — скажи ему нажать кнопку «📋 Оставить заявку»."""
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

NAME, PHONE, DESCRIPTION, CONFIRM = range(4)
chat_histories = {}


def save_order(order: dict) -> int:
    file_exists = os.path.isfile(CSV_FILE)
    order_id = 1
    if file_exists:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) > 1:
                order_id = int(rows[-1][0]) + 1
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["#", "Дата", "Имя", "Телефон", "Описание", "Статус"])
        writer.writerow([order_id, datetime.now().strftime("%Y-%m-%d %H:%M"),
                         order["name"], order["phone"], order["description"], "Новая"])
    return order_id


async def ask_ai(user_id: int, message: str) -> str:
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    chat_histories[user_id].append({"role": "user", "content": message})
    if len(chat_histories[user_id]) > 10:
        chat_histories[user_id] = chat_histories[user_id][-10:]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.kie.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "claude-haiku-4-5",
                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *chat_histories[user_id]],
                    "max_tokens": 500,
                },
            )
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            chat_histories[user_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.error(f"Ошибка KIE AI: {e}")
        return "Извините, ИИ временно недоступен. Попробуйте позже."


async def generate_image(prompt: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.kie.ai/v1/images/generations",
                headers={"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"},
                json={"model": "wan2.7-i2v", "prompt": prompt, "n": 1, "size": "1024x1024"},
            )
            data = response.json()
            image_url = data["data"][0]["url"]
            img_response = await client.get(image_url)
            return img_response.content
    except Exception as e:
        logger.error(f"Ошибка генерации картинки: {e}")
        return None


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📋 Оставить заявку", "🎨 Сгенерировать картинку"], ["📞 Связаться с нами"]],
    resize_keyboard=True
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Привет! Я умный помощник.\n\n"
        "Могу:\n• Ответить на любой вопрос 🤖\n• Принять заявку 📋\n• Нарисовать картинку 🎨\n\n"
        "Чем могу помочь?",
        reply_markup=MAIN_KEYBOARD,
    )


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📞 Для связи: @your_username\n⏰ Работаем: пн–пт, 9:00–18:00")


async def image_generation_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎨 Опишите что хотите нарисовать (желательно на английском).\n\nНапример: *a beautiful sunset over mountains*",
        parse_mode="Markdown",
    )
    context.user_data["waiting_for_image"] = True


async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["waiting_for_image"] = False
    await update.message.reply_text(
        "Оформим заявку!\n\nШаг 1/3: Введите ваше *имя*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Шаг 2/3: Введите ваш *номер телефона*:", parse_mode="Markdown")
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Шаг 3/3: Опишите вашу *заявку или задачу*:", parse_mode="Markdown")
    return DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text
    summary = (f"📋 *Проверьте данные:*\n\n"
               f"👤 Имя: {context.user_data['name']}\n"
               f"📞 Телефон: {context.user_data['phone']}\n"
               f"📝 Заявка: {context.user_data['description']}\n\nВсё верно?")
    await update.message.reply_text(
        summary, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["✅ Подтвердить", "✏️ Заново"], ["❌ Отмена"]], resize_keyboard=True),
    )
    return CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = save_order(context.user_data)
    await update.message.reply_text(
        f"✅ *Заявка №{order_id} принята!*\n\nСвяжемся с вами в ближайшее время. Спасибо! 🙏",
        parse_mode="Markdown", reply_markup=MAIN_KEYBOARD,
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"🔔 *Новая заявка №{order_id}*\n\n"
                 f"👤 {context.user_data['name']}\n📞 {context.user_data['phone']}\n"
                 f"📝 {context.user_data['description']}\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления: {e}")
    context.user_data.clear()
    return ConversationHandler.END


async def restart_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Начнём заново.\n\nШаг 1/3: Введите ваше *имя*:", parse_mode="Markdown")
    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Отменено. Чем ещё могу помочь?", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    user_id = update.effective_user.id

    if context.user_data.get("waiting_for_image"):
        context.user_data["waiting_for_image"] = False
        await update.message.reply_text("🎨 Генерирую картинку, подождите 10-30 секунд...")
        image_bytes = await generate_image(text)
        if image_bytes:
            await update.message.reply_photo(photo=image_bytes, caption=f"🎨 «{text}»")
        else:
            await update.message.reply_text("😔 Не удалось сгенерировать. Попробуйте другое описание.")
        return

    await update.message.chat.send_action("typing")
    reply = await ask_ai(user_id, text)
    await update.message.reply_text(reply)


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Только для администратора.")
        return
    if not os.path.isfile(CSV_FILE):
        await update.message.reply_text("Заявок пока нет.")
        return
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return
    text = "📋 *Последние заявки:*\n\n"
    for r in reversed(rows[-5:]):
        text += f"*№{r['#']}* | {r['Дата']}\n👤 {r['Имя']} | 📞 {r['Телефон']}\n📝 {r['Описание'][:60]}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📋 Оставить заявку$"), new_order_start)],
        states={
            NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            CONFIRM: [
                MessageHandler(filters.Regex("^✅ Подтвердить$"), confirm_order),
                MessageHandler(filters.Regex("^✏️ Заново$"), restart_order),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ Отмена$"), cancel), CommandHandler("cancel", cancel)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", list_orders))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^🎨 Сгенерировать картинку$"), image_generation_start))
    app.add_handler(MessageHandler(filters.Regex("^📞 Связаться с нами$"), contact_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
