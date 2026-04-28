
import os
import json
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = Path("data/hashtags.json")


def load_tags():
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_tags(tags):
    DATA_FILE.write_text(
        json.dumps(tags, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "HashtagBot PRO läuft auf BOTMaster 😎\n\n"
        "Befehle:\n"
        "/add #tag Text\n"
        "/remove #tag\n"
        "/list\n"
        "/ping"
    )


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong ✅")


async def add_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    parts = text.split(maxsplit=2)

    if len(parts) < 3:
        await update.message.reply_text("Format: /add #tag Antworttext")
        return

    tag = parts[1].lower()
    response = parts[2]

    if not tag.startswith("#"):
        await update.message.reply_text("Der Tag muss mit # beginnen.")
        return

    tags = load_tags()
    tags[tag] = response
    save_tags(tags)

    await update.message.reply_text(f"Gespeichert ✅\n{tag}")


async def remove_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split(maxsplit=1)

    if len(parts) < 2:
        await update.message.reply_text("Format: /remove #tag")
        return

    tag = parts[1].lower()
    tags = load_tags()

    if tag not in tags:
        await update.message.reply_text("Tag nicht gefunden.")
        return

    del tags[tag]
    save_tags(tags)

    await update.message.reply_text(f"Gelöscht ✅\n{tag}")


async def list_tags(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tags = load_tags()

    if not tags:
        await update.message.reply_text("Noch keine Hashtags gespeichert.")
        return

    text = "Gespeicherte Hashtags:\n\n"
    for tag in sorted(tags.keys()):
        text += f"{tag}\n"

    await update.message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.lower()
    tags = load_tags()

    for tag, response in tags.items():
        if tag in text:
            await update.message.reply_text(response)
            return


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN fehlt in .env")

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("add", add_tag))
    app.add_handler(CommandHandler("remove", remove_tag))
    app.add_handler(CommandHandler("list", list_tags))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("HashtagBot PRO startet...")
    app.run_polling()


if __name__ == "__main__":
    main()
