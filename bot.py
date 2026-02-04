import os
import requests
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

TOKEN = os.environ.get("TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕌 Ramazan Vakit Botu\n\n"
        "Komutlar:\n"
        "/iftar ankara → İftara kaç dakika kaldı\n"
        "/sahur ankara → Sahura kaç dakika kaldı\n\n"
        "Hayırlı Ramazanlar 🤲"
    )

def get_vakit(city):
    url = f"https://ezanvakti.herokuapp.com/vakitler?il={city}"
    res = requests.get(url).json()
    return res[0]

def dakika_hesapla(vakit_str):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)

    vakit = datetime.strptime(vakit_str, "%H:%M").replace(
        year=now.year,
        month=now.month,
        day=now.day,
        tzinfo=tz
    )

    return int((vakit - now).total_seconds() / 60)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /iftar ankara")
        return

    city = context.args[0].capitalize()
    vakitler = get_vakit(city)
    dakika = dakika_hesapla(vakitler["Aksam"])

    if dakika > 0:
        msg = f"📍 {city}\n🍽️ İftara {dakika} dakika kaldı"
    else:
        msg = f"📍 {city}\n🌙 İftar vakti girdi ya da geçti"

    await update.message.reply_text(msg)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /sahur ankara")
        return

    city = context.args[0].capitalize()
    vakitler = get_vakit(city)
    dakika = dakika_hesapla(vakitler["Imsak"])

    if dakika > 0:
        msg = f"📍 {city}\n🌙 Sahura {dakika} dakika kaldı"
    else:
        msg = f"📍 {city}\n⏰ Sahur vakti geçti"

    await update.message.reply_text(msg)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))

    app.run_polling()

if __name__ == "__main__":
    main()
