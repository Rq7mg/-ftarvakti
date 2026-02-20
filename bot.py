import os
import json
import requests
import random
import asyncio
import pytz
from datetime import datetime, timedelta
from pymongo import MongoClient
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# =========================
# AYARLAR (Config)
# =========================
TOKEN = os.environ.get("TOKEN") 
MONGO_URI = os.environ.get("MONGO_URI") 
ADMIN_IDS = [6563936773]
HADIS_DOSYA = "hadisler.json"

# =========================
# 1. MONGODB VE VERİ
# =========================
try:
    client = MongoClient(MONGO_URI)
    db = client["ramazan_botu"]
    chats_col = db["chats"]
except Exception as e:
    print(f"❌ MongoDB Hatası: {e}")

def load_json(dosya):
    if os.path.exists(dosya):
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

HADISLER = load_json(HADIS_DOSYA) or [{"metin": "Oruç tutunuz ki sıhhat bulasınız.", "kaynak": "Taberânî"}]

# =========================
# 2. YARDIMCI ARAÇLAR (PROFESYONEL)
# =========================

def progress_bar(current_seconds, total_seconds=86400):
    """Vakte ne kadar kaldığını görsel bir bar ile gösterir."""
    size = 10
    # Oruç süresi yaklaşık 14-16 saat olduğu için barı ona göre oranlıyoruz
    filled = int((1 - (current_seconds / 57600)) * size) 
    filled = max(0, min(size, filled))
    return "▬" * filled + "🔘" + "▬" * (size - filled)

def get_prayertimes(city):
    try:
        headers = {'User-Agent': 'KiyiciZeminBot/6.0'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        geo_req = requests.get(geo_url, headers=headers, timeout=10)
        geo_data = geo_req.json()
        if not geo_data: return None, None, None
        
        lat, lon = geo_data[0]['lat'], geo_data[0]['lon']
        gercek_yer = geo_data[0]['display_name'].split(",")[0]

        aladhan_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        r = requests.get(aladhan_url, timeout=10)
        data = r.json()
        return data["data"]["timings"], data["data"]["meta"]["timezone"], gercek_yer
    except: return None, None, None

def time_until(vakit_str, tz_name):
    target_tz = pytz.timezone(tz_name)
    now_local = datetime.now(target_tz)
    h, m = map(int, vakit_str.split(" ")[0].split(":"))
    vakit_time = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    if now_local >= vakit_time: vakit_time += timedelta(days=1)
    delta = vakit_time - now_local
    ts = int(delta.total_seconds())
    return ts // 3600, (ts % 3600) // 60, vakit_str.split(" ")[0], ts

# =========================
# 3. ZENGİN İÇERİKLİ KOMUTLAR
# =========================

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("📍 <b>Şehir belirtmedin bebenin gülü!</b>\nÖrn: <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)
    
    city = " ".join(context.args)
    timings, tz, yer = get_prayertimes(city)
    if not timings: return await update.message.reply_text("❌ Şehir bulunamadı.")

    h, m, saat, total_sec = time_until(timings["Maghrib"], tz)
    bar = progress_bar(total_sec)

    mesaj = (
        f"<b>✨ İFTAR VAKTİ | {yer.upper()}</b>\n"
        f"<code>{datetime.now().strftime('%d %B %Y')}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🌅 <b>Akşam Ezanı:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <code>{h} saat {m} dakika</code>\n"
        f"<code>{bar}</code>\n\n"
        f"🤲 <b>İftar Duası:</b>\n"
        f"<i>'Allahümme leke sumtü ve bike âmentü ve aleyke tevekkeltü ve alâ rızkıke eftartü.'</i>\n\n"
        f"🥖 <b>Sofranız bereketli, dualarınız kabul olsun gardaşım.</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("📍 <b>Şehri yazmayı unutma la bebe!</b>", parse_mode=ParseMode.HTML)
        
    city = " ".join(context.args)
    timings, tz, yer = get_prayertimes(city)
    if not timings: return await update.message.reply_text("❌ Şehir bulunamadı.")

    h, m, saat, total_sec = time_until(timings["Fajr"], tz)
    bar = progress_bar(total_sec)

    mesaj = (
        f"<b>🌙 SAHUR (İMSAK) | {yer.upper()}</b>\n"
        f"<code>{datetime.now().strftime('%d %B %Y')}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📢 <b>İmsak Vakti:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <code>{h} saat {m} dakika</code>\n"
        f"<code>{bar}</code>\n\n"
        f"💡 <b>Günün Hatırlatması:</b>\n"
        f"<i>'Sahur yapın, zira sahurda bereket vardır.' (Hadis-i Şerif)</i>\n\n"
        f"💧 <b>Niyet etmeyi ve su içmeyi unutma!</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# =========================
# 4. YÖNETİM VE DİĞER (Öncekiyle Aynı)
# =========================

async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        chats_col.update_one({"chat_id": update.effective_chat.id}, {"$set": {"chat_id": update.effective_chat.id, "type": str(update.effective_chat.type)}}, upsert=True)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    u = chats_col.count_documents({"type": "private"})
    g = chats_col.count_documents({"type": {"$in": ["group", "supergroup"]}})
    await update.message.reply_text(f"📊 <b>İstatistikler</b>\n👤 Kullanıcı: {u}\n👥 Grup: {g}", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return await update.message.reply_text("Metin yok!")
    chats = list(chats_col.find({}))
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=text, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Duyuru tamam.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, radar_handler), group=0)
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.run_polling()

if __name__ == "__main__":
    main()
