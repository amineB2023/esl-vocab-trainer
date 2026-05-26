import csv
import random
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from datetime import datetime
from pathlib import Path
from typing import Iterator


DB_PATH = Path("vocab_trainer.db")
DATA_DIR = Path("data")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                level TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        add_user_progress_columns(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                word TEXT NOT NULL,
                definition TEXT NOT NULL,
                example TEXT NOT NULL,
                UNIQUE(level, word)
            )
            """
        )


def add_user_progress_columns(connection: sqlite3.Connection) -> None:
    cursor = connection.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "correct_answers" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN correct_answers INTEGER NOT NULL DEFAULT 0"
        )
    if "wrong_answers" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN wrong_answers INTEGER NOT NULL DEFAULT 0"
        )
    if "streak_days" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN streak_days INTEGER NOT NULL DEFAULT 0"
        )
    if "xp" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN xp INTEGER NOT NULL DEFAULT 0")
    if "streak" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN streak INTEGER NOT NULL DEFAULT 0")
        if "streak_days" in existing_columns:
            connection.execute("UPDATE users SET streak = streak_days")
    if "last_active_date" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN last_active_date TEXT")
    if "reminder_enabled" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN reminder_enabled INTEGER NOT NULL DEFAULT 0"
        )
    if "reminder_hour" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN reminder_hour INTEGER NOT NULL DEFAULT 8"
        )


def save_user_level(telegram_id: int, level: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (telegram_id, level)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                level = excluded.level,
                updated_at = CURRENT_TIMESTAMP
            """,
            (telegram_id, level),
        )


def get_user_level(telegram_id: int) -> str | None:
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT level FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_user_progress(telegram_id: int) -> dict[str, int]:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT correct_answers, wrong_answers, streak, xp
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return {
            "words_learned": 0,
            "correct_answers": 0,
            "wrong_answers": 0,
            "accuracy": 0,
            "streak": 0,
            "xp": 0,
        }

    correct_answers = row[0]
    wrong_answers = row[1]
    total_answers = correct_answers + wrong_answers
    accuracy = round((correct_answers / total_answers) * 100) if total_answers else 0

    return {
        "words_learned": total_answers,
        "correct_answers": correct_answers,
        "wrong_answers": wrong_answers,
        "accuracy": accuracy,
        "streak": row[2],
        "xp": row[3],
    }


def update_daily_activity(telegram_id: int) -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)

    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT streak, last_active_date FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = cursor.fetchone()
        cursor.close()

        if row is None:
            return

        current_streak = row[0]
        last_active_date = row[1]

        if last_active_date == today.isoformat():
            new_streak = current_streak
        elif last_active_date == yesterday.isoformat():
            new_streak = current_streak + 1
        else:
            new_streak = 1

        connection.execute(
            """
            UPDATE users
            SET xp = xp + 10,
                streak = ?,
                last_active_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (new_streak, today.isoformat(), telegram_id),
        )


def set_reminder(telegram_id: int, enabled: bool) -> bool:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE users
            SET reminder_enabled = ?,
                reminder_hour = 8,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (1 if enabled else 0, telegram_id),
        )
        updated_rows = cursor.rowcount

    return updated_rows > 0


def get_users_due_for_reminder(current_hour: int | None = None) -> list[int]:
    if current_hour is None:
        current_hour = datetime.now().hour

    with get_connection() as connection:
        cursor = connection.execute(
            """
            SELECT telegram_id
            FROM users
            WHERE reminder_enabled = 1
              AND reminder_hour = ?
            """,
            (current_hour,),
        )
        rows = cursor.fetchall()

    return [row[0] for row in rows]


def import_words_from_csv_files(data_dir: Path = DATA_DIR) -> None:
    csv_files = sorted(data_dir.glob("*_words.csv"))

    with get_connection() as connection:
        cursor = connection.execute("PRAGMA table_info(words)")
        word_columns = {row[1] for row in cursor.fetchall()}
        has_old_option_columns = {"option_a", "option_b", "option_c", "correct_option"}.issubset(
            word_columns
        )

        for csv_file in csv_files:
            with csv_file.open("r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if has_old_option_columns:
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO words (
                                level,
                                word,
                                definition,
                                example,
                                option_a,
                                option_b,
                                option_c,
                                correct_option
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                row["level"],
                                row["word"],
                                row["definition"],
                                row["example"],
                                row["word"],
                                "",
                                "",
                                "A",
                            ),
                        )
                    else:
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO words (
                                level,
                                word,
                                definition,
                                example
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                row["level"],
                                row["word"],
                                row["definition"],
                                row["example"],
                            ),
                        )


def get_words_by_level(level: str, limit: int = 5) -> list[dict[str, str]]:
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            SELECT word, definition, example
            FROM words
            WHERE level = ?
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (level, limit),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_word_by_id(word_id: int) -> dict[str, str] | None:
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            SELECT id, word, definition, example
            FROM words
            WHERE id = ?
            """,
            (word_id,),
        )
        row = cursor.fetchone()

    if row is None:
        return None

    return dict(row)


def get_quiz_question(level: str) -> dict[str, object] | None:
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            """
            SELECT id, word, definition
            FROM words
            WHERE level = ?
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (level,),
        )
        correct_word = cursor.fetchone()

        if correct_word is None:
            return None

        cursor = connection.execute(
            """
            SELECT word
            FROM words
            WHERE level = ? AND id != ?
            ORDER BY RANDOM()
            LIMIT 2
            """,
            (level, correct_word["id"]),
        )
        other_words = cursor.fetchall()

    options = [correct_word["word"]] + [row["word"] for row in other_words]
    random.shuffle(options)

    return {
        "id": correct_word["id"],
        "word": correct_word["word"],
        "definition": correct_word["definition"],
        "options": options,
    }


def update_quiz_progress(telegram_id: int, is_correct: bool) -> None:
    column = "correct_answers" if is_correct else "wrong_answers"
    xp_earned = 5 if is_correct else 1

    with get_connection() as connection:
        connection.execute(
            f"""
            UPDATE users
            SET {column} = {column} + 1,
                xp = xp + ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (xp_earned, telegram_id),
        )
