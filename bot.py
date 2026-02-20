import os
import json
import requests
import asyncio
import pytz
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR
# =========================
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# =========================
# 🚀 HIZLANDIRILMIŞ ŞEHİR MOTORU
# =========================
def get_prayertimes(city_input):
    if not city_input: return None
    
    # Türkçe Karakter Dönüşümü (API'nin anlaması için)
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    # En hızlı API endpointi
    url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
    
    try:
        # Hız için timeout 5 saniyeye çekildi
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("data"):
                return {
                    "vakitler": data["data"]["timings"], 
                    "timezone": data["data"]["meta"]["timezone"], 
                    "yer": city_input.upper() # Kullanıcının yazdığı gibi büyük harf
                }
    except:
        return None
    return None

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat(chat_id, chat_type):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": str(chat_type)})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🎭 ANA MOTOR (HIZLI RENDER)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("📍 Örn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)

    # API sorgusu
    data = get_prayertimes(city)
    
    if not data:
        return await update.message.reply_text(f"❌ <b>'{city}'</b> şehri bulunamadı.\nLütfen yazımı kontrol edin.")

    # Vakit Hesaplama
    tz = pytz.timezone(data["timezone"])
    now = datetime.now(tz)
    target_str = data["vakitler"][mode]
    target = now.replace(hour=int(target_str.split(":")[0]), minute=int(target_str.split(":")[1]), second=0)
    
    if now >= target: target += timedelta(days=1)
    diff = target - now
    sec = int(diff.total_seconds())
    
    # Görsel Bar
    bar_size = 10
    progress = min(1, max(0, 1 - (sec / 57600)))
    filled = int(bar_size * progress)
    bar = "🌕" * filled + "🌑" * (bar_size - filled)

    header = "İFTAR VAKTİ" if mode == "Maghrib" else "SAHUR VAKTİ"
    mesaj = (
        f"✨ <b>{header} | {data['yer']}</b> ✨\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
        f"⏳ <b>Kalan:</b> <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
        f"<code>{bar}</code>  <b>%{int(progress*100)}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🤲 <i>Hayırlı Ramazanlar.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ DİĞER KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat(update.effective_chat.id, update.effective_chat.type)
    await update.message.reply_text("⚜️ <b>Hoş Geldiniz!</b>\nŞehir ismini Türkçe harflerle yazabilirsiniz.\nÖrn: <code>/iftar Şanlıurfa</code>", parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Toplam Kullanıcı: {len(load_chats())}")

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    chats = load_chats()
    for c in chats:
        try: await context.bot.send_message(c["chat_id"], f"📢 {text}")
        except: pass

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat(u.effective_chat.id, u.effective_chat.type)))
    app.run_polling()

if __name__ == "__main__":
    main()
