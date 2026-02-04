import os
import json
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")

# --------------------------
# ADMIN user id (duyuru için)
# --------------------------
ADMIN_IDS = [6563936773, 6030484208]

# --------------------------
# Chat ID saklama dosyası
# --------------------------
CHAT_FILE = "chats.json"

def kaydet_chat_id(chat_id):
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                chats = json.load(f)
        else:
            chats = []

        if chat_id not in chats:
            chats.append(chat_id)
            with open(CHAT_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f)
    except Exception as e:
        print("chat_id kaydetme hatası:", e)

def get_all_chats():
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except:
        return []

# --------------------------
# Diyanet API fonksiyonları
# --------------------------
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
        return data[0]  # Bugünün vakitleri
    except Exception as e:
        print("get_prayertimes HATA:", e)
        return None

# --------------------------
# ZAMAN HESAPLARI (DÜZELTİLDİ)
# --------------------------
def diff_minutes_today(vakit_str):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)

    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

    return int((vakit_time - now).total_seconds() / 60)

def diff_minutes_sahur(vakit_str):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)

    h, m = map(int, vakit_str.split(":"))
    imsak_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

    # Eğer şu an imsak saatini geçtiyse → yarının imsağı
    if now >= imsak_time:
        imsak_time += timedelta(days=1)

    return int((imsak_time - now).total_seconds() / 60)

# --------------------------
# /start
# --------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    kaydet_chat_id(chat_id)
    await update.message.reply_text(
        "🕌 Diyanet İftar & Sahur Vakti Botu hazır!\n\n"
        "Komutlar:\n"
        "/iftar <şehir>\n"
        "/sahur <şehir>\n"
        "/duyuru <mesaj> → Bot yöneticisi için\n"
        "/hadis → Rastgele hadis\n"
        "/ramazan → Ramazan günü veya kaç gün kaldı"
    )

# --------------------------
# /iftar
# --------------------------
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
    diff = diff_minutes_today(maghrib)

    if diff > 0:
        await update.message.reply_text(
            f"📍 {city.title()}\n🍽️ İftara {diff} dakika kaldı"
        )
    else:
        await update.message.reply_text(
            f"📍 {city.title()}\n🌙 İftar vakti girdi veya geçti"
        )

# --------------------------
# /sahur
# --------------------------
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
    diff = diff_minutes_sahur(fajr)

    await update.message.reply_text(
        f"📍 {city.title()}\n🌙 Sahura {diff} dakika kaldı"
    )

# --------------------------
# /duyuru
# --------------------------
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Bu komutu sadece bot yöneticisi kullanabilir.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /duyuru <mesaj>")
        return

    mesaj = " ".join(context.args)
    chats = get_all_chats()
    count = 0

    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id, f"📢 Duyuru:\n\n{mesaj}")
            count += 1
        except Exception as e:
            print("Duyuru gönderilemedi:", chat_id, e)

    await update.message.reply_text(f"Duyuru gönderildi! ({count} chat)")

# --------------------------
# Yeni komutlar için import
# --------------------------
from handlers.hadis import hadis
from handlers.ramazan import ramazan

# --------------------------
# Main
# --------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    # Yeni eklenen komutlar
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("ramazan", ramazan))

    print("Bot başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
