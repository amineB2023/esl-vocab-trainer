import logging
import os
import random
import re

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database import (
    class_code_exists,
    create_class,
    get_quiz_question,
    get_students_for_teacher,
    get_teacher_classes,
    get_user_class,
    get_user_level,
    get_user_progress,
    get_users_due_for_reminder,
    get_words_by_level,
    get_word_by_id,
    import_words_from_csv_files,
    init_db,
    is_teacher,
    join_class,
    save_user_level,
    save_user_profile,
    set_reminder,
    update_daily_activity,
    update_quiz_progress,
)


LEVELS = ("A1", "A2", "B1", "B2")
(
    CREATE_CLASS_SCHOOL,
    CREATE_CLASS_NAME,
    CREATE_CLASS_TEACHER,
    CREATE_CLASS_WELCOME,
) = range(4)
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
    BotCommand("help", "How to use the bot"),
]

DAILY_BUTTON = "📚 Daily"
QUIZ_BUTTON = "🧠 Quiz"
PROGRESS_BUTTON = "📊 Progress"
SETTINGS_BUTTON = "⚙️ Settings"
MY_CLASS_BUTTON = "🏫 My Class"
CHANGE_LEVEL_BUTTON = "🎚 Change Level"
REMINDER_BUTTON = "⏰ Reminder"
REMINDER_ON_BUTTON = "🔔 Reminder On"
REMINDER_OFF_BUTTON = "🔕 Reminder Off"
BACK_BUTTON = "⬅️ Back"
STUDENTS_BUTTON = "👥 Students"
MY_CLASSES_BUTTON = "🏫 My Classes"
CREATE_CLASS_BUTTON = "➕ Create Class"
TEACHER_TOOLS_BUTTON = "⚙️ Teacher Tools"
CLASS_REPORT_BUTTON = "📊 Class Report"
SEND_REMINDER_BUTTON = "📢 Send Reminder"


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


def student_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [DAILY_BUTTON, QUIZ_BUTTON, PROGRESS_BUTTON],
            [SETTINGS_BUTTON, MY_CLASS_BUTTON],
        ],
        resize_keyboard=True,
    )


def student_settings_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [CHANGE_LEVEL_BUTTON, REMINDER_BUTTON],
            [BACK_BUTTON],
        ],
        resize_keyboard=True,
    )


def reminder_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [REMINDER_ON_BUTTON, REMINDER_OFF_BUTTON],
            [BACK_BUTTON],
        ],
        resize_keyboard=True,
    )


def teacher_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [DAILY_BUTTON, QUIZ_BUTTON, STUDENTS_BUTTON],
            [MY_CLASSES_BUTTON, CREATE_CLASS_BUTTON],
            [TEACHER_TOOLS_BUTTON],
        ],
        resize_keyboard=True,
    )


def teacher_tools_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [CLASS_REPORT_BUTTON, SEND_REMINDER_BUTTON],
            [BACK_BUTTON],
        ],
        resize_keyboard=True,
    )


def user_menu_keyboard(telegram_id: int) -> ReplyKeyboardMarkup:
    if is_teacher(telegram_id):
        return teacher_menu_keyboard()

    return student_menu_keyboard()


async def require_teacher(update: Update) -> bool:
    if is_teacher(update.effective_user.id):
        return True

    await update.message.reply_text(
        "❌ Teacher access required.",
        reply_markup=student_menu_keyboard(),
    )
    return False


def escape_markdown(text: str) -> str:
    for character in ("\\", "_", "*", "`", "["):
        text = text.replace(character, f"\\{character}")
    return text


def word_emoji(word: str) -> str:
    if word.lower() in WORD_EMOJIS:
        return WORD_EMOJIS[word.lower()]

    return random.choice(DEFAULT_WORD_EMOJIS)


def class_code_part(text: str, fallback: str) -> str:
    match = re.search(r"[A-Za-z0-9]+", text.upper())
    if match is None:
        return fallback

    return match.group(0)[:10]


def generate_class_code(school_name: str, class_name: str) -> str:
    school_part = class_code_part(school_name, "CLASS")
    class_part = class_code_part(class_name, "")

    for _ in range(20):
        number = random.randint(100, 999)
        if class_part:
            class_code = f"{school_part}-{class_part}-{number}"
        else:
            class_code = f"{school_part}-{number}"

        if not class_code_exists(class_code):
            return class_code

    return f"CLASS-{random.randint(1000, 9999)}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    save_user_profile(user.id, first_name=user.first_name, username=user.username)
    class_info = get_user_class(user.id)

    if class_info:
        teacher_name = class_info.get("teacher_name") or "Your teacher"
        welcome_message = (
            class_info.get("welcome_message")
            or "Today's English practice is ready."
        )
        await update.message.reply_text(
            f"🏫 Welcome to {class_info['school_name']}\n\n"
            f"Teacher: {teacher_name}\n"
            f"Class: {class_info['class_name']}\n\n"
            f"{welcome_message}",
            reply_markup=user_menu_keyboard(user.id),
        )
        return

    await update.message.reply_text(
        "✨ Welcome to ESL Vocabulary Trainer!\n\n"
        "Use the keyboard below to practice every day.\n\n"
        "If you have a class code from your teacher, send:\n"
        "/join YOUR-CODE",
        reply_markup=user_menu_keyboard(update.effective_user.id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📚 *English Vocab Trainer*\n\n"
        "Use the menu below to practice every day.\n\n"
        "📖 Today's Vocabulary - Learn 5 words\n"
        "🧠 Quiz - Test yourself\n"
        "📊 Progress - View XP, streak, and accuracy\n"
        "🎚 Level - Change A1/A2/B1/B2\n"
        "🔔 Reminder - Turn daily reminders on/off\n"
        "🏫 Classes - Create or join a class with Telegram",
        parse_mode="Markdown",
        reply_markup=user_menu_keyboard(update.effective_user.id),
    )


async def create_class_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if not await require_teacher(update):
        return ConversationHandler.END

    await update.message.reply_text("Enter school name")
    return CREATE_CLASS_SCHOOL


async def create_class_school(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data["school_name"] = update.message.text.strip()
    await update.message.reply_text("Enter class name")
    return CREATE_CLASS_NAME


async def create_class_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data["class_name"] = update.message.text.strip()
    await update.message.reply_text("Enter teacher name")
    return CREATE_CLASS_TEACHER


async def create_class_teacher(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    context.user_data["teacher_name"] = update.message.text.strip()
    await update.message.reply_text("Enter welcome message")
    return CREATE_CLASS_WELCOME


async def create_class_welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    school_name = context.user_data.get("school_name", "").strip()
    class_name = context.user_data.get("class_name", "").strip()
    teacher_name = context.user_data.get("teacher_name", "").strip()
    welcome_message = update.message.text.strip()
    class_code = generate_class_code(school_name, class_name)

    create_class(
        class_code=class_code,
        school_name=school_name,
        class_name=class_name,
        teacher_name=teacher_name,
        welcome_message=welcome_message,
        teacher_telegram_id=update.effective_user.id,
    )
    context.user_data.pop("school_name", None)
    context.user_data.pop("class_name", None)
    context.user_data.pop("teacher_name", None)

    await update.message.reply_text(
        "✅ Class created!\n\n"
        f"School: {school_name}\n"
        f"Class: {class_name}\n"
        f"Teacher: {teacher_name}\n"
        f"Class Code: {class_code}\n\n"
        "Students can join with:\n"
        f"/join {class_code}",
        reply_markup=teacher_menu_keyboard(),
    )
    return ConversationHandler.END


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Please send a class code like:\n/join CLASS-9284")
        return

    class_code = context.args[0].strip().upper()
    user = update.effective_user
    class_info = join_class(
        telegram_id=user.id,
        class_code=class_code,
        first_name=user.first_name,
        username=user.username,
    )

    if class_info is None:
        await update.message.reply_text(
            "❌ Class code not found. Please check with your teacher."
        )
        return

    await update.message.reply_text(
        f"✅ You joined {class_info['school_name']} - {class_info['class_name']}",
        reply_markup=student_menu_keyboard(),
    )


async def my_class(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_teacher(update.effective_user.id):
        teacher_classes = get_teacher_classes(update.effective_user.id)
        lines = ["🏫 Your Classes"]
        for class_info in teacher_classes:
            lines.append(
                f"\nSchool: {class_info['school_name']}\n"
                f"Class: {class_info['class_name']}\n"
                f"Code: {class_info['class_code']}"
            )
        await update.message.reply_text("\n".join(lines))
        return

    class_info = get_user_class(update.effective_user.id)
    if class_info is None:
        await update.message.reply_text("You have not joined a class yet.")
        return

    await update.message.reply_text(
        "🏫 School:\n"
        f"{class_info['school_name']}\n\n"
        "👥 Class:\n"
        f"{class_info['class_name']}\n\n"
        "🎓 Role: Student"
    )


async def class_students(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_teacher(update):
        return

    rows = get_students_for_teacher(update.effective_user.id)
    if not rows:
        await update.message.reply_text("No classes found. Create one with /create_class")
        return

    classes: dict[str, dict[str, object]] = {}
    for row in rows:
        class_code = str(row["class_code"])
        if class_code not in classes:
            classes[class_code] = {
                "title": f"{row['school_name']} - {row['class_name']}",
                "students": [],
            }

        if row["telegram_id"] is None:
            continue

        if row["username"]:
            student_name = f"@{row['username']}"
        elif row["first_name"]:
            student_name = row["first_name"]
        else:
            student_name = str(row["telegram_id"])

        classes[class_code]["students"].append(student_name)

    messages = ["👥 Class Students"]
    for class_code, class_data in classes.items():
        messages.append(f"\n{class_data['title']}\nCode: {class_code}")
        students = class_data["students"]
        if students:
            for index, student in enumerate(students, start=1):
                messages.append(f"{index}. {student}")
        else:
            messages.append("No students yet.")

    await update.message.reply_text("\n".join(messages))


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
    class_info = get_user_class(update.effective_user.id)
    class_code = class_info["class_code"] if class_info else None

    if user_level is None:
        await update.message.reply_text("Please choose your level first with /start")
        return

    words = get_words_by_level(user_level, limit=5, class_code=class_code)
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
    class_info = get_user_class(update.effective_user.id)
    class_code = class_info["class_code"] if class_info else None

    if user_level is None:
        await update.message.reply_text("Please choose your level first with /start")
        return

    question = get_quiz_question(user_level, class_code=class_code)
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


async def handle_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    teacher_only_buttons = {
        STUDENTS_BUTTON,
        MY_CLASSES_BUTTON,
        TEACHER_TOOLS_BUTTON,
        CLASS_REPORT_BUTTON,
        SEND_REMINDER_BUTTON,
    }

    if text in teacher_only_buttons and not await require_teacher(update):
        return

    if text == DAILY_BUTTON:
        await daily(update, context)
    elif text == QUIZ_BUTTON:
        await quiz(update, context)
    elif text == PROGRESS_BUTTON:
        await progress(update, context)
    elif text in (MY_CLASS_BUTTON, MY_CLASSES_BUTTON):
        await my_class(update, context)
    elif text == STUDENTS_BUTTON:
        await class_students(update, context)
    elif text == SETTINGS_BUTTON:
        await update.message.reply_text(
            "⚙️ Settings\n\nChoose what you want to update.",
            reply_markup=student_settings_keyboard(),
        )
    elif text == CHANGE_LEVEL_BUTTON:
        await level(update, context)
    elif text == REMINDER_BUTTON:
        await update.message.reply_text(
            "⏰ Reminder\n\nTurn your daily vocabulary reminder on or off.",
            reply_markup=reminder_keyboard(),
        )
    elif text == REMINDER_ON_BUTTON:
        await reminder_on(update, context)
    elif text == REMINDER_OFF_BUTTON:
        await reminder_off(update, context)
    elif text == TEACHER_TOOLS_BUTTON:
        if not await require_teacher(update):
            return
        await update.message.reply_text(
            "⚙️ Teacher Tools\n\nChoose a class action.",
            reply_markup=teacher_tools_keyboard(),
        )
    elif text == CLASS_REPORT_BUTTON:
        if not await require_teacher(update):
            return
        await update.message.reply_text("📊 Class reports are coming soon.")
    elif text == SEND_REMINDER_BUTTON:
        if not await require_teacher(update):
            return
        await update.message.reply_text("📢 Class reminder sending is coming soon.")
    elif text == BACK_BUTTON:
        await update.message.reply_text(
            "Main menu",
            reply_markup=user_menu_keyboard(update.effective_user.id),
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
    create_class_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("create_class", create_class_start),
            MessageHandler(
                filters.Regex(f"^{re.escape(CREATE_CLASS_BUTTON)}$"),
                create_class_start,
            ),
        ],
        states={
            CREATE_CLASS_SCHOOL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_class_school)
            ],
            CREATE_CLASS_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_class_name)
            ],
            CREATE_CLASS_TEACHER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_class_teacher)
            ],
            CREATE_CLASS_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_class_welcome)
            ],
        },
        fallbacks=[],
    )

    application.add_handler(create_class_conversation)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("level", level))
    application.add_handler(CommandHandler("progress", progress))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("my_class", my_class))
    application.add_handler(CommandHandler("class_students", class_students))
    application.add_handler(CommandHandler("reminder_on", reminder_on))
    application.add_handler(CommandHandler("reminder_off", reminder_off))
    application.add_handler(CallbackQueryHandler(handle_level_choice, pattern=r"^level:"))
    application.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern=r"^quiz:"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_button))

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue is not available. Install python-telegram-bot[job-queue]."
        )
    application.job_queue.run_repeating(send_daily_reminders, interval=3600, first=10)

    logger.info("Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
