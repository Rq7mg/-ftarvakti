import os
import json
import requests
import random
import asyncio
import pytz
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# 🛡️ LOG & TOKEN
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# =========================
# 🚀 KESİNTİSİZ ŞEHİR MOTORU (v17)
# =========================
def get_prayertimes(city_input):
    if not city_input: return None
    
    # Adım 1: Türkçe karakterleri tamamen temizle
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    # Adım 2: Alternatif isimler (Örn: istanbul -> istanbul)
    # Bazı API'ler 'istanbul' bazıları 'istambul' bekleyebilir ama genel standart 'istanbul'dur.
    
    try:
        # Aladhan API - En stabil endpoint
        api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
        res = requests.get(api_url, timeout=15)
        
        if res.status_code == 200:
            data = res.json()
            if "data" in data:
                return {
                    "vakitler": data["data"]["timings"], 
                    "timezone": data["data"]["meta"]["timezone"], 
                    "yer": city_input.upper()
                }
        
        # Eğer ilk sorgu başarısız olursa (Örn: Şanlıurfa), boşluksuz dene
        city_no_space = city_clean.replace(" ", "")
        api_url_2 = f"https://api.aladhan.com/v1/timingsByCity?city={city_no_space}&country=Turkey&method=13"
        res2 = requests.get(api_url_2, timeout=10)
        if res2.status_code == 200:
            data = res2.json()
            return {
                "vakitler": data["data"]["timings"], 
                "timezone": data["data"]["meta"]["timezone"], 
                "yer": city_input.upper()
            }
            
        return None
    except Exception as e:
        logger.error(f"API Hatası: {e}")
        return None

# =========================
# 📊 VERİ & DOSYA SİSTEMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat_async(chat_id, chat_type):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%d.%m.%Y")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=4)
    except: pass

# =========================
# 🎮 ANA MOTOR
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("📍 Lütfen bir şehir ismi yazın.\nÖrn: <code>/iftar Bursa</code>", parse_mode=ParseMode.HTML)

    # API Sorgusu Başlat
    data = get_prayertimes(city)
    
    if not data:
        # Şehir bulunamazsa Admin'e log at ve kullanıcıya bilgi ver
        logger.warning(f"Şehir Bulunamadı: {city}")
        return await update.message.reply_text(
            f"❌ <b>'{city}'</b> şehri sistemde bulunamadı.\n\n"
            f"💡 <b>İpucu:</b> Şehir ismini Türkçe karakter kullanmadan yazmayı deneyebilirsiniz.\n"
            f"Örn: <code>/iftar Sanliurfa</code> veya <code>/iftar Istanbul</code>", 
            parse_mode=ParseMode.HTML
        )

    # Vakit Hesaplama
    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        
        # İlerleme Çubuğu
        size = 12
        total_p = 57600 if mode == "Maghrib" else 28800
        progress = min(1, max(0, 1 - (sec / total_p)))
        filled = int(size * progress)
        bar = "🌕" * filled + "🌑" * (size - filled)

        header = "🌙 İFTAR VAKTİ" if mode == "Maghrib" else "🥣 SAHUR VAKTİ"
        mesaj = (
            f"✨ <b>{header} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b>  <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b>  <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(progress*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"🤲 <i>Hayırlı Ramazanlar.</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Render Hatası: {e}")

# =========================
# 🛠️ ADMIN & DİĞER KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat_async(update.effective_chat.id, update.effective_chat.type)
    await update.message.reply_text(
        "✨ <b>Ramazan Elite v17 Aktif!</b>\n\n"
        "Şehir yazarak vakitleri öğrenebilirsiniz.\n"
        "Örn: <code>/iftar İstanbul</code>\n"
        "Örn: <code>/sahur Ankara</code>", 
        parse_mode=ParseMode.HTML
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = len(load_chats())
    await update.message.reply_text(f"📊 Toplam Kullanıcı: {count}")

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text: return
    chats = load_chats()
    for c in chats:
        try: await context.bot.send_message(chat_id=c["chat_id"], text=f"📢 {text}")
        except: pass
    await update.message.reply_text("✅ Gönderildi.")

# =========================
# 🚀 BAŞLAT
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat_async(u.effective_chat.id, u.effective_chat.type)))
    
    print("🚀 v17 FINAL DEPLOYED.")
    app.run_polling()

if __name__ == "__main__":
    main()
