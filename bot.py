import logging
import os
import random

from dotenv import load_dotenv
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from database import (
    get_quiz_question,
    get_user_level,
    get_user_progress,
    get_users_due_for_reminder,
    get_words_by_level,
    get_word_by_id,
    import_words_from_csv_files,
    init_db,
    save_user_level,
    set_reminder,
    update_daily_activity,
    update_quiz_progress,
)


LEVELS = ("A1", "A2", "B1", "B2")
WORD_EMOJIS = {
    "apple": "🍎",
    "book": "📖",
    "borrow": "🤝",
    "city": "🏙️",
    "drink": "🥤",
    "eat": "🍽️",
    "family": "👨‍👩‍👧‍👦",
    "friend": "🤝",
    "happy": "😊",
    "house": "🏠",
    "improve": "📈",
    "journey": "🧳",
    "language": "💬",
    "learn": "🧠",
    "market": "🛒",
    "plan": "🗓️",
    "read": "📖",
    "school": "🏫",
    "speak": "🗣️",
    "study": "📚",
    "travel": "✈️",
    "water": "💧",
}
DEFAULT_WORD_EMOJIS = ["✨", "🌟", "💬", "🧠", "📌", "🚀"]
BOT_COMMANDS = [
    BotCommand("start", "Start the bot"),
    BotCommand("daily", "Today's vocabulary"),
    BotCommand("quiz", "Take a quiz"),
    BotCommand("progress", "View progress"),
    BotCommand("level", "Change level"),
    BotCommand("reminder_on", "Turn on daily reminder"),
    BotCommand("reminder_off", "Turn off daily reminder"),
    BotCommand("help", "How to use the bot"),
]


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def level_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(level, callback_data=f"level:{level}")]
        for level in LEVELS
    ]
    return InlineKeyboardMarkup(buttons)


def escape_markdown(text: str) -> str:
    for character in ("\\", "_", "*", "`", "["):
        text = text.replace(character, f"\\{character}")
    return text


def word_emoji(word: str) -> str:
    if word.lower() in WORD_EMOJIS:
        return WORD_EMOJIS[word.lower()]

    return random.choice(DEFAULT_WORD_EMOJIS)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to ESL Vocabulary Trainer!\n\nChoose your English level:",
        reply_markup=level_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📚 *English Vocab Trainer*\n\n"
        "Use the menu below to practice every day.\n\n"
        "📖 Today's Vocabulary - Learn 5 words\n"
        "🧠 Quiz - Test yourself\n"
        "📊 Progress - View XP, streak, and accuracy\n"
        "🎚 Level - Change A1/A2/B1/B2\n"
        "🔔 Reminder - Turn daily reminders on/off",
        parse_mode="Markdown",
    )


async def level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Choose your new English level:",
        reply_markup=level_keyboard(),
    )


async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_progress = get_user_progress(update.effective_user.id)

    await update.message.reply_text(
        "📊 *Your Progress*\n\n"
        f"⭐ XP: {user_progress['xp']}\n"
        f"🔥 Streak: {user_progress['streak']} days\n"
        f"📚 Words learned: {user_progress['words_learned']}\n"
        f"✅ Correct answers: {user_progress['correct_answers']}\n"
        f"❌ Wrong answers: {user_progress['wrong_answers']}\n"
        f"🎯 Accuracy: {user_progress['accuracy']}%",
        parse_mode="Markdown",
    )


async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_level = get_user_level(update.effective_user.id)

    if user_level is None:
        await update.message.reply_text("Please choose your level first with /start")
        return

    words = get_words_by_level(user_level, limit=5)
    if not words:
        await update.message.reply_text(
            "No words found for your level yet. Please try again later."
        )
        return

    update_daily_activity(update.effective_user.id)

    messages = ["📚 *Today's Vocabulary*", "━━━━━━━━━━"]
    number_icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    for index, word in enumerate(words):
        vocabulary_word = escape_markdown(word["word"].title())
        definition = escape_markdown(word["definition"])
        example = escape_markdown(word["example"])

        messages.append(
            f"*{number_icons[index]} {vocabulary_word}* {word_emoji(word['word'])}\n"
            f"💡 *Meaning:* {definition}\n"
            f"📝 *Example:* _{example}_"
        )
        messages.append("━━━━━━━━━━")

    messages.append("✨ *Challenge:*\nTry using at least *2 new words* today!")

    await update.message.reply_text("\n\n".join(messages), parse_mode="Markdown")


async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_level = get_user_level(update.effective_user.id)

    if user_level is None:
        await update.message.reply_text("Please choose your level first with /start")
        return

    question = get_quiz_question(user_level)
    if question is None:
        await update.message.reply_text(
            "No quiz words found for your level yet. Please try again later."
        )
        return

    option_letters = ("A", "B", "C")
    option_lines = []
    buttons = []

    for letter, option in zip(option_letters, question["options"]):
        option_lines.append(f"{letter}. {option}")
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{letter}. {option}",
                    callback_data=f"quiz:{question['id']}:{option}",
                )
            ]
        )

    await update.message.reply_text(
        "🧠 Vocabulary Quiz\n\n"
        "💡 Meaning:\n"
        f"{question['definition']}\n\n"
        "Choose the correct word:\n\n"
        + "\n".join(option_lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def reminder_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    was_updated = set_reminder(update.effective_user.id, enabled=True)

    if not was_updated:
        await update.message.reply_text("Please choose your level first with /start")
        return

    await update.message.reply_text(
        "🔔 Daily reminder is ON.\n"
        "I'll remind you every day at 8:00 AM."
    )


async def reminder_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    was_updated = set_reminder(update.effective_user.id, enabled=False)

    if not was_updated:
        await update.message.reply_text("Please choose your level first with /start")
        return

    await update.message.reply_text("🔕 Daily reminder is OFF.")


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ids = get_users_due_for_reminder()

    for telegram_id in user_ids:
        await context.bot.send_message(
            chat_id=telegram_id,
            text="📚 Time for your daily vocabulary!\nUse /daily to learn today's words.",
        )


async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    _, word_id, selected_word = query.data.split(":", maxsplit=2)
    correct_word = get_word_by_id(int(word_id))

    if correct_word is None:
        await query.edit_message_text("This quiz question is no longer available.")
        return

    is_correct = selected_word.lower() == correct_word["word"].lower()
    update_quiz_progress(query.from_user.id, is_correct)

    if is_correct:
        await query.edit_message_text(
            "✅ Correct!\n"
            f"{correct_word['word'].title()} = {correct_word['definition']}"
        )
        return

    await query.edit_message_text(
        "❌ Not quite.\n"
        f"Correct answer: {correct_word['word']}"
    )


async def handle_level_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    level_value = query.data.split(":", maxsplit=1)[1]
    if level_value not in LEVELS:
        await query.edit_message_text("Invalid level. Please use /level to choose again.")
        return

    user = query.from_user
    save_user_level(telegram_id=user.id, level=level_value)

    await query.edit_message_text(
        f"Your level has been saved as {level_value}.\n\n"
        "Use /progress to see your progress."
    )


async def register_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")

    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Add it to your .env file.")

    init_db()
    import_words_from_csv_files()

    application = (
        Application.builder()
        .token(token)
        .post_init(register_bot_commands)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("level", level))
    application.add_handler(CommandHandler("progress", progress))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("reminder_on", reminder_on))
    application.add_handler(CommandHandler("reminder_off", reminder_off))
    application.add_handler(CallbackQueryHandler(handle_level_choice, pattern=r"^level:"))
    application.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern=r"^quiz:"))

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue is not available. Install python-telegram-bot[job-queue]."
        )
    application.job_queue.run_repeating(send_daily_reminders, interval=3600, first=10)

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
