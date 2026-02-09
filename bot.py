import os
import json
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import random

TOKEN = os.environ.get("TOKEN")

ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"

# =========================
# JSON'dan hadis yükleme
# =========================
HADIS_DOSYA = "hadisler.json"

def load_json(dosya):
    try:
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ {dosya} bulunamadı.")
        return []

HADISLER = load_json(HADIS_DOSYA)

# --------------------------
# Mevcut diğer kodlar (chat kaydetme, normalize, iftar, sahur vb.) aynen kalacak
# --------------------------
def kaydet_chat_id(chat_id, chat_type):
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                chats = json.load(f)
        else:
            chats = []

        if not any(c["chat_id"] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": chat_type})
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

def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower()

def find_location_id(city):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0].get("id")
    except:
        return None

def get_prayertimes(location_id):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None
    except:
        return None

tz = pytz.timezone("Europe/Istanbul")

def time_until(vakit_str, next_day_if_passed=False):
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if next_day_if_passed and now >= vakit_time:
        vakit_time += timedelta(days=1)
    delta = vakit_time - now
    total_minutes = int(delta.total_seconds() / 60)
    return total_minutes // 60, total_minutes % 60, vakit_time.strftime("%H:%M")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    await update.message.reply_text(
        "🕌 Diyanet İftar & Sahur Vakti Botu hazır!\n\n"
        "/iftar <şehir>\n"
        "/sahur <şehir>\n"
        "/duyuru → Yanıtladığın mesajı duyuru yapar\n"
        "/hadis\n"
        "/ramazan"
    )

async def kaydet_mesaj_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /iftar <şehir>")
        return
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return
    times = get_prayertimes(loc_id)
    maghrib = times.get("maghrib")
    h, m, saat = time_until(maghrib, True)
    await update.message.reply_text(f"📍 {city_input}\n🍽️ İftara {h} saat {m} dakika kaldı ({saat})")

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /sahur <şehir>")
        return
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return
    times = get_prayertimes(loc_id)
    fajr = times.get("fajr")
    h, m, saat = time_until(fajr, True)
    await update.message.reply_text(f"📍 {city_input}\n🌙 Sahura {h} saat {m} dakika kaldı ({saat})")

# ==========================
# DÜZELTİLMİŞ /DUYURU
# ==========================
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Lütfen duyuru yapmak için bir mesaja yanıt ver.")
        return

    reply = update.message.reply_to_message
    chats = get_all_chats()
    basarili = 0

    for chat in chats:
        try:
            if reply.text:
                await context.bot.send_message(chat["chat_id"], f"📢 DUYURU\n\n{reply.text}")

            elif reply.photo:
                await context.bot.send_photo(
                    chat["chat_id"],
                    photo=reply.photo[-1].file_id,
                    caption=reply.caption or "📢 DUYURU"
                )

            elif reply.video:
                await context.bot.send_video(
                    chat["chat_id"],
                    video=reply.video.file_id,
                    caption=reply.caption or "📢 DUYURU"
                )

            basarili += 1
        except:
            pass

    await update.message.reply_text(f"✅ Duyuru gönderildi.\n📨 Ulaşılan chat sayısı: {basarili}")

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    start = datetime(2026, 2, 19).date()
    end = datetime(2026, 3, 19).date()
    if now < start:
        await update.message.reply_text(f"🌙 Ramazan’a {(start - now).days} gün kaldı.")
    elif now > end:
        await update.message.reply_text("🌙 Ramazan sona erdi.")
    else:
        await update.message.reply_text(f"🌙 Bugün Ramazan’ın {(now - start).days + 1}. günü.")

# ==========================
# GÜNCELLENMİŞ /HADİS KOMUTU
# ==========================
async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("⚠️ Hadis bulunamadı.")
        return

    secilen = random.choice(HADISLER)  # JSON’daki tüm hadisler havuzdan rastgele seçilir
    mesaj = f"📜 Hadis-i Şerif\n\n“{secilen['metin']}”\n\nKaynak: {secilen['kaynak']}"
    await update.message.reply_text(mesaj)

# ==========================
# BOTU BAŞLATMA
# ==========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kaydet_mesaj_chat))
    print("Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
