import os
import requests
from datetime import datetime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Telegram bot token
TOKEN = os.environ.get("TOKEN")

# API URL (Heroku env değişkeni ile güvenli)
EZAN_API_URL = os.environ.get("EZAN_API_URL", "https://ezanvakti.herokuapp.com/vakitler?il=")

# --------------------------
# İmsakiye verisi çek
# --------------------------
def get_vakit(city: str):
    try:
        city = city.capitalize()
        url = f"{EZAN_API_URL}{city}"
        print("API URL:", url)
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0]
    except Exception as e:
        print("get_vakit HATA:", e)
        return None

# --------------------------
# Dakika hesapla
# --------------------------
def dakika_hesapla(vakit_str: str):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    try:
        h, m = map(int, vakit_str.split(":"))
        vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        return int((vakit_time - now).total_seconds() / 60)
    except Exception as e:
        print("dakika_hesapla HATA:", e)
        return None

# --------------------------
# /start komutu
# --------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕌 Ramazan Vakit Botu\n\n"
        "Komutlar:\n"
        "/iftar <şehir> → İftara kaç dk kaldı\n"
        "/sahur <şehir> → Sahura kaç dk kaldı\n\n"
        "Hayırlı Ramazanlar 🤲"
    )

# --------------------------
# /iftar komutu
# --------------------------
async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("Kullanım: /iftar <şehir>")
            return

        city = context.args[0].lower()
        vakitler = get_vakit(city)

        if not vakitler:
            await update.message.reply_text("Vakit verisi alınamadı veya şehir hatalı.")
            return

        aksam = vakitler.get("Aksam")
        diff = dakika_hesapla(aksam)
        if diff is None:
            await update.message.reply_text("İftar saati hesaplanamadı.")
            return

        if diff > 0:
            msg = f"📍 {city.title()}\n🍽️ İftara {diff} dakika kaldı"
        else:
            msg = f"📍 {city.title()}\n🌙 İftar vakti girdi veya geçti"

        await update.message.reply_text(msg)

    except Exception as e:
        print("iftar HATA:", e)
        await update.message.reply_text("Bir hata oluştu. Lütfen tekrar deneyin.")

# --------------------------
# /sahur komutu
# --------------------------
async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("Kullanım: /sahur <şehir>")
            return

        city = context.args[0].lower()
        vakitler = get_vakit(city)

        if not vakitler:
            await update.message.reply_text("Vakit verisi alınamadı veya şehir hatalı.")
            return

        imsak = vakitler.get("Imsak")
        diff = dakika_hesapla(imsak)
        if diff is None:
            await update.message.reply_text("Sahur saati hesaplanamadı.")
            return

        if diff > 0:
            msg = f"📍 {city.title()}\n🌙 Sahura {diff} dakika kaldı"
        else:
            msg = f"📍 {city.title()}\n⏰ Sahur vakti geçti"

        await update.message.reply_text(msg)

    except Exception as e:
        print("sahur HATA:", e)
        await update.message.reply_text("Bir hata oluştu. Lütfen tekrar deneyin.")

# --------------------------
# Main
# --------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))

    print("Bot başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
