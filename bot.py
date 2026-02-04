import os
import requests
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

def find_location_id(city):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0].get("id")
    except Exception as e:
        print("find_location_id HATA:", e)
        return None

def get_prayertimes(location_id):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        # İlk gün (bugün)
        return data[0]
    except Exception as e:
        print("get_prayertimes HATA:", e)
        return None

def diff_minutes(vakit_str):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    try:
        h, m = map(int, vakit_str.split(":"))
        vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return int((vakit_time - now).total_seconds() / 60)
    except Exception as e:
        print("diff_minutes HATA:", e)
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕌 Diyanet Namaz Vakiti Botu Hazır!\n\n"
        "/iftar <şehir>\n"
        "/sahur <şehir>"
    )

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /iftar <şehir>")
        return

    city = context.args[0]
    loc_id = find_location_id(city)
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return

    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("Namaz vakitleri alınamadı.")
        return

    maghrib = times.get("maghrib") or times.get("Maghrib")
    diff = diff_minutes(maghrib)
    if diff is None:
        await update.message.reply_text("İftar saati hesaplanamadı.")
        return

    if diff > 0:
        await update.message.reply_text(f"📍 {city.title()}\n🍽️ İftara {diff} dakika kaldı")
    else:
        await update.message.reply_text(f"📍 {city.title()}\n🌙 İftar vakti girdi veya geçti")

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /sahur <şehir>")
        return

    city = context.args[0]
    loc_id = find_location_id(city)
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return

    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("Namaz vakitleri alınamadı.")
        return

    fajr = times.get("fajr") or times.get("Fajr")
    diff = diff_minutes(fajr)
    if diff is None:
        await update.message.reply_text("Sahur saati hesaplanamadı.")
        return

    if diff > 0:
        await update.message.reply_text(f"📍 {city.title()}\n🌙 Sahura {diff} dakika kaldı")
    else:
        await update.message.reply_text(f"📍 {city.title()}\n⏰ Sahur vakti geçti")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))

    app.run_polling()

if __name__ == "__main__":
    main()
