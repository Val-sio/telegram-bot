"""
Telegram-бот для приёма и обработки заявок
Зависимости: pip install python-telegram-bot
"""

import csv
import logging
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# ─── Настройки ───────────────────────────────────────────────────────────────
BOT_TOKEN = "8610613129:AAGtDbgtyxigBi3E_BaRb7R6DpI-HQvh3cc"   # получить у @BotFather
ADMIN_CHAT_ID = 1150947024 
CSV_FILE = "orders.csv"
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Шаги диалога
NAME, PHONE, DESCRIPTION, CONFIRM = range(4)


def save_order(order: dict) -> int:
    """Сохраняет заявку в CSV и возвращает её номер."""
    file_exists = os.path.isfile(CSV_FILE)
    order_id = 1

    if file_exists:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            if len(rows) > 1:           # есть строки кроме заголовка
                order_id = int(rows[-1][0]) + 1

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["#", "Дата", "Имя", "Телефон", "Описание", "Статус"])
        writer.writerow([
            order_id,
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            order["name"],
            order["phone"],
            order["description"],
            "Новая",
        ])

    return order_id


# ─── Обработчики ─────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["📋 Оставить заявку"], ["📞 Связаться с нами"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Привет! Я помогу принять вашу заявку.\n\n"
        "Нажмите *«Оставить заявку»*, чтобы начать.",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📞 Для связи: @your_username\n"
        "⏰ Работаем: пн–пт, 9:00–18:00"
    )


async def new_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Отлично! Давайте оформим заявку.\n\n"
        "Шаг 1/3: Введите ваше *имя*:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True),
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Шаг 2/3: Введите ваш *номер телефона*:",
        parse_mode="Markdown",
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["phone"] = update.message.text
    await update.message.reply_text(
        "Шаг 3/3: Опишите вашу *заявку или задачу*:",
        parse_mode="Markdown",
    )
    return DESCRIPTION


async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text

    summary = (
        f"📋 *Проверьте данные:*\n\n"
        f"👤 Имя: {context.user_data['name']}\n"
        f"📞 Телефон: {context.user_data['phone']}\n"
        f"📝 Заявка: {context.user_data['description']}\n\n"
        f"Всё верно?"
    )
    keyboard = [["✅ Подтвердить", "✏️ Заполнить заново"], ["❌ Отмена"]]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return CONFIRM


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = save_order(context.user_data)

    # Уведомление пользователю
    await update.message.reply_text(
        f"✅ *Заявка №{order_id} принята!*\n\n"
        f"Мы свяжемся с вами в ближайшее время.\n"
        f"Спасибо, {context.user_data['name']}! 🙏",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([["📋 Оставить заявку"]], resize_keyboard=True),
    )

    # Уведомление администратору
    admin_msg = (
        f"🔔 *Новая заявка №{order_id}*\n\n"
        f"👤 Имя: {context.user_data['name']}\n"
        f"📞 Телефон: {context.user_data['phone']}\n"
        f"📝 Описание: {context.user_data['description']}\n"
        f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_msg,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администратору: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def restart_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Хорошо, начнём заново.\n\nШаг 1/3: Введите ваше *имя*:",
        parse_mode="Markdown",
    )
    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    keyboard = [["📋 Оставить заявку"], ["📞 Связаться с нами"]]
    await update.message.reply_text(
        "Заявка отменена. Если передумаете — я здесь! 👋",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )
    return ConversationHandler.END


# ─── Команда /orders — список заявок (только для админа) ─────────────────────

async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Эта команда только для администратора.")
        return

    if not os.path.isfile(CSV_FILE):
        await update.message.reply_text("Заявок пока нет.")
        return

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        await update.message.reply_text("Заявок пока нет.")
        return

    # Последние 5 заявок
    recent = rows[-5:]
    text = "📋 *Последние заявки:*\n\n"
    for r in reversed(recent):
        text += (
            f"*№{r['#']}* | {r['Дата']}\n"
            f"👤 {r['Имя']} | 📞 {r['Телефон']}\n"
            f"📝 {r['Описание'][:60]}{'...' if len(r['Описание']) > 60 else ''}\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Запуск ──────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 Оставить заявку$"), new_order_start)
        ],
        states={
            NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_description)],
            CONFIRM: [
                MessageHandler(filters.Regex("^✅ Подтвердить$"), confirm_order),
                MessageHandler(filters.Regex("^✏️ Заполнить заново$"), restart_order),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            CommandHandler("cancel", cancel),
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("orders", list_orders))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^📞 Связаться с нами$"), contact_info))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
