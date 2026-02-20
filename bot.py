import os
import json
import requests
import random
import asyncio
import pytz
import locale
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

# Tarih formatını Türkçe yapmaya çalış (Heroku/Linux desteği için)
try:
    locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
except:
    pass

# =========================
# 1. MONGODB VE VERİ YÖNETİMİ
# =========================
try:
    client = MongoClient(MONGO_URI)
    db = client["ramazan_botu"]
    chats_col = db["chats"]
    print("✅ MongoDB Bağlantısı Zımba Gibi!")
except Exception as e:
    print(f"❌ MongoDB Hatası: {e}")

def load_json(dosya):
    if os.path.exists(dosya):
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

HADISLER = load_json(HADIS_DOSYA) or [
    {"metin": "Oruç tutunuz ki sıhhat bulasınız.", "kaynak": "Taberânî"},
    {"metin": "Ramazan ayı sabır ayıdır; sabrın sevabı ise cennetir.", "kaynak": "Münzirî"},
    {"metin": "Kim bir oruçluya iftar ettirirse, kendisine onun sevabı kadar sevap yazılır.", "kaynak": "Tirmizî"}
]

# =========================
# 2. AKILLI YARDIMCI ARAÇLAR
# =========================

def get_progress_bar(current_sec, total_sec):
    """Görsel olarak zenginleştirilmiş ilerleme çubuğu."""
    bar_length = 12
    progress = min(1, max(0, 1 - (current_sec / total_sec)))
    filled_length = int(bar_length * progress)
    bar = "▓" * filled_length + "░" * (bar_length - filled_length)
    percentage = int(progress * 100)
    return f"<code>{bar}</code> %{percentage}"

def get_prayertimes(city):
    try:
        headers = {'User-Agent': 'KiyiciZeminBot/Pro_v7'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        geo_data = requests.get(geo_url, headers=headers, timeout=10).json()
        if not geo_data: return None
        
        lat, lon = geo_data[0]['lat'], geo_data[0]['lon']
        yer_adi = geo_data[0]['display_name'].split(",")[0]
        
        api_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        data = requests.get(api_url, timeout=10).json()
        return {
            "vakitler": data["data"]["timings"],
            "timezone": data["data"]["meta"]["timezone"],
            "yer": yer_adi
        }
    except: return None

def time_calc(target_time_str, tz_name):
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    h, m = map(int, target_time_str.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now >= target: target += timedelta(days=1)
    diff = target - now
    sec = int(diff.total_seconds())
    return sec // 3600, (sec % 3600) // 60, target_time_str, sec

# =========================
# 3. GÖSTERİŞLİ KOMUTLAR
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Radar otomatik kaydediyor ama start'ta da sağlama alalım
    if update.effective_chat:
        chats_col.update_one({"chat_id": update.effective_chat.id}, {"$set": {"chat_id": update.effective_chat.id, "type": str(update.effective_chat.type)}}, upsert=True)
    
    welcome_text = (
        "<b>🌙 Ramazan-ı Şerif Rehberine Hoş Geldin!</b>\n\n"
        "Senin için her şeyi düşündüm gardaş. Dünyanın neresinde olursan ol, vakitleri saniyesi saniyesine söylerim.\n\n"
        "🚀 <b>Neler Yapabilirim?</b>\n"
        "├ 🍽 /iftar <code>şehir</code> - İftara ne kaldı?\n"
        "├ 🥣 /sahur <code>şehir</code> - Sahur vakti ne zaman?\n"
        "├ 📜 /hadis - Ruhuna gıda ver.\n"
        "├ 📅 /ramazan - Ramazan sayacı.\n"
        "└ 🤲 /dua - Günün iftar duası.\n\n"
        "<i>Hadi, bir şehir yaz da başlayalım!</i>"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("📍 <b>Hangi şehir bebenin gülü?</b>\nÖrn: <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)
    
    city = " ".join(context.args)
    data = get_prayertimes(city)
    if not data: return await update.message.reply_text("❌ <b>Bu şehri haritada bulamadım gardaş!</b>")

    h, m, saat, sec = time_calc(data["vakitler"]["Maghrib"], data["timezone"])
    bar = get_progress_bar(sec, 57600) # Yaklaşık 16 saatlik oruç baz alındı

    mesaj = (
        f"<b>🕌 İFTAR VAKTİ | {data['yer'].upper()}</b>\n"
        f"📅 <code>{datetime.now().strftime('%d %B %Y')}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🕔 <b>Akşam Ezanı:</b>  <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b>   <code>{h} saat {m} dakika</code>\n\n"
        f"<b>İlerleme Durumu:</b>\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🤲 <b>Günün Duası:</b>\n<i>'Allah'ım! Senin rızan için oruç tuttum, Sana inandım, Sana güvendim.'</i>\n\n"
        f"✨ <i>Hayırlı İftarlar, Rabbim kabul etsin!</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("📍 <b>Şehri yaz da sahurda aç kalma!</b>", parse_mode=ParseMode.HTML)
    
    city = " ".join(context.args)
    data = get_prayertimes(city)
    if not data: return await update.message.reply_text("❌ Şehir bulunamadı.")

    h, m, saat, sec = time_calc(data["vakitler"]["Fajr"], data["timezone"])
    bar = get_progress_bar(sec, 28800) # 8 saatlik gece baz alındı

    mesaj = (
        f"<b>🌙 SAHUR VAKTİ | {data['yer'].upper()}</b>\n"
        f"📅 <code>{datetime.now().strftime('%d %B %Y')}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📢 <b>İmsak Vakti:</b>  <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b>   <code>{h} saat {m} dakika</code>\n\n"
        f"<b>Güne Hazırlık:</b>\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"💡 <i>Unutma: Sahurda bereket vardır. Niyet etmeyi ve suyunu içmeyi ihmal etme bebenin gülü!</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 2026 Ramazan Başlangıcı: 19 Şubat
    now = datetime.now(pytz.timezone("Europe/Istanbul")).date()
    start_date = datetime(2026, 2, 19).date()
    end_date = datetime(2026, 3, 19).date()
    
    if now < start_date:
        diff = (start_date - now).days
        msg = f"<b>⏳ Sabır Gardaş!</b>\n\nOn bir ayın sultanına kavuşmaya son <b>{diff} gün</b> kaldı. Hazırlıkları tamamla!"
    elif now > end_date:
        msg = "<b>👋 Elveda Ya Şehr-i Ramazan...</b>\n\nRabbim tekrarına, sağlıkla ve huzurla kavuştursun. Bayramın mübarek olsun!"
    else:
        gun = (now - start_date).days + 1
        msg = f"<b>🌙 RAMAZAN-I ŞERİF</b>\n\nBugün kutsal ayın <b>{gun}. günündeyiz</b>. Dualarda buluşalım."
    
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    h = random.choice(HADISLER)
    await update.message.reply_text(f"<b>📜 GÜNÜN HADİS-İ ŞERİFİ</b>\n\n<i>\"{h['metin']}\"</i>\n\n📍 Kaynak: <b>{h['kaynak']}</b>", parse_mode=ParseMode.HTML)

# =========================
# 4. YÖNETİCİ & RADAR (KEMİK KADRO)
# =========================

async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        chats_col.update_one(
            {"chat_id": update.effective_chat.id}, 
            {"$set": {"chat_id": update.effective_chat.id, "type": str(update.effective_chat.type)}}, 
            upsert=True
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    u = chats_col.count_documents({"type": "private"})
    g = chats_col.count_documents({"type": {"$in": ["group", "supergroup"]}})
    
    mesaj = (
        "<b>📊 SİSTEM PANELİ (ADMIN)</b>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"👤 <b>Kullanıcı:</b> <code>{u}</code>\n"
        f"👥 <b>Grup:</b> <code>{g}</code>\n"
        f"📈 <b>Toplam:</b> <code>{u+g}</code>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "<i>Radar sistemi aktif, veri tabanı stabil.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return await update.message.reply_text("❌ Duyuru metni boş olamaz!")

    chats = list(chats_col.find({}))
    await update.message.reply_text(f"🚀 Duyuru {len(chats)} adrese postalanıyor...")
    
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=text, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ İşlem tamamlandı.")

# =========================
# 5. ANA ÇALIŞTIRICI
# =========================

def main():
    if not TOKEN or not MONGO_URI:
        print("❌ HATA: TOKEN veya MONGO_URI eksik! Heroku ayarlarını kontrol et.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Radar (Tüm mesajları yakalayıp kaydeder)
    app.add_handler(MessageHandler(filters.ALL, radar_handler), group=0)
    
    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    print("🚀 BOT MARŞA BASTI! Ramazan Modu Aktif.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
