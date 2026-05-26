# ESL Vocabulary Trainer Bot

A simple Telegram vocabulary trainer bot MVP built with Python, python-telegram-bot, python-dotenv, and SQLite.

## Features

- `/start` command with a welcome message
- Telegram bot menu commands
- Inline level buttons: A1, A2, B1, B2
- Saves each user's Telegram ID and selected level in SQLite
- `/level` command to change level
- `/daily` command with 5 sample words from the user's level
- `/quiz` command with multiple-choice vocabulary questions
- `/progress` command with XP, streak, answers, and accuracy
- `/reminder_on` and `/reminder_off` commands for daily vocabulary reminders
- `/help` command with usage guidance
- Teacher class codes with `/create_class`
- Student class joining with `/join CLASSCODE`
- Class lookup with `/my_class` and `/class_students`

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create your environment file:

```bash
copy .env.example .env
```

4. Add your Telegram bot token to `.env`:

```env
BOT_TOKEN=your_real_bot_token_here
```

5. Run the bot:

```bash
python bot.py
```

The bot will create `vocab_trainer.db` automatically on startup and import the sample words from the `data` folder.

## Commands

- `/start` - Start the bot and choose a level
- `/help` - Show how to use the bot
- `/level` - Change your level
- `/daily` - Get 5 vocabulary words for your level
- `/quiz` - Answer a multiple-choice vocabulary question
- `/progress` - Show placeholder progress
- `/reminder_on` - Enable the daily 8:00 AM vocabulary reminder
- `/reminder_off` - Disable the daily vocabulary reminder
- `/create_class` - Create a Telegram class code
- `/join CLASSCODE` - Join a class with your teacher's code
- `/my_class` - View your class details
- `/class_students` - View students who joined your class
