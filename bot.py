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

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8610613129:AAGtDbgtyxigBi3E_BaRb7R6DpI-HQvh3cc")
ADMIN_CHAT_ID = 1150947024
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
CSV_FILE = "orders.csv"

SYSTEM_PROMPT = """Ты умный помощник в Telegram-боте.
Отвечай кратко, дружелюбно и по делу на русском языке.
Помогаешь клиентам с вопросами и принимаешь заявки.
Если клиент хочет оставить заявку — скажи ему нажать кнопку «📋 Оставить заявку»."""

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

NAME, PHONE, DESCRIPTION, CONFIRM = range(4)
chat_histories = {}


def save_order(order):
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


async def ask_ai(user_id, message):
    if not OPENROUTER_API_KEY:
        return "ИИ не настроен. Обратитесь к администратору."
    if user_id not in chat_histories:
        chat_histories[user_id] = []
    chat_histories[user_id].append({"role": "user", "content": message})
    if len(chat_histories[user_id]) > 10:
        chat_histories[user_id] = chat_histories[user_id][-10:]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://telegram.org",
                },
                json={
                    "model": "meta-llama/llama-3.1-8b-instruct:free",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        *chat_histories[user_id],
                    ],
                    "max_tokens": 500,
                },
            )
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            chat_histories[user_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.error(f"Ошибка ИИ: {e}")
        return "Извините, ИИ временно недоступен. Попробуйте позже."


MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["📋 Оставить заявку", "🎨 Сгенерировать картинку"], ["📞 Связаться с нами"]],
    resize_keyboard=True
)


async def start(update, context):
    await update.message.reply_text(
        "👋 Привет! Я умный помощник.\n\n"
        "Могу:\n• Ответить на любой вопрос 🤖\n• Принять заявку 📋\n\n"
        "Чем могу помочь?",
        reply_markup=MAIN_KEYBOARD,
    )


async def contact_info(update, context):
    await update.message.reply_text("📞 Для связи: @your_username\n⏰ Работаем: пн–пт, 9:00–18:00")


async def new_order_start(update, context):
    await update.message.reply_text(
        "Оформим заявку!\n\nШаг 1/3: Введите ваше *имя*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
    )
    return NAME


async def get_name(update, context):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Шаг 2/3: Введите ваш *номер телефона*:", parse_mode="Markdown")
    return PHONE


async def get_phone(update, context):
    context.user_data["phone"] = update.message.text
    await update.message.reply_text("Шаг 3/3: Опишите вашу *заявку или задачу*:", parse_mode="Markdown")
    return DESCRIPTION


async def get_description(update, context):
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


async def confirm_order(update, context):
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


async def restart_order(update, context):
    context.user_data.clear()
    await update.message.reply_text("Начнём заново.\n\nШаг 1/3: Введите ваше *имя*:", parse_mode="Markdown")
    return NAME


async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("Отменено. Чем ещё могу помочь?", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def handle_message(update, context):
    text = update.message.text
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")
    reply = await ask_ai(user_id, text)
    await update.message.reply_text(reply)


async def list_orders(update, context):
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


def main():
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
    app.add_handler(MessageHandler(filters.Regex("^📞 Связаться с нами$"), contact_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
