import os
import json
import requests
import asyncio
import pytz
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# 🛡️ GÜVENLİK VE LOG
# =========================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# =========================
# 🚀 JET HIZINDA API MOTORU
# =========================
def get_prayertimes(city_input):
    if not city_input: return None
    
    # Türkçe harfleri hem küçültüp hem API formatına sokuyoruz
    # Ama sana gösterirken orijinal halini koruyoruz!
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    # Hız için en yakın Aladhan lokasyonu ve metot 13 (Diyanet'e en yakını)
    url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
    
    try:
        # Hız için timeout 4 saniyeye çekildi, başarısızsa saniyelerce beklemez
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if data.get("data"):
                return {
                    "vakitler": data["data"]["timings"], 
                    "timezone": data["data"]["meta"]["timezone"], 
                    "yer": city_input.title() # Yazdığın gibi (örn: Şanlıurfa)
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
# 🎭 ANA MOTOR (ANLIK YANIT)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("📍 <b>Lütfen şehir yazın.</b>\nÖrn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)

    # API Sorgusu (Jet Hızıyla)
    data = get_prayertimes(city)
    
    if not data:
        return await update.message.reply_text(f"❌ <b>'{city}'</b> bulunamadı.\nLütfen yazımı kontrol edin (Örn: Iğdır, Şanlıurfa).")

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        target = now.replace(hour=int(target_str.split(":")[0]), minute=int(target_str.split(":")[1]), second=0)
        
        if now >= target: target += timedelta(days=1)
        diff = target - now
        sec = int(diff.total_seconds())
        
        # Elite Progress Bar (12'li sistem)
        progress = min(1, max(0, 1 - (sec / 57600)))
        filled = int(12 * progress)
        bar = "🔵" * filled + "⚪" * (12 - filled)

        header = "🌙 İFTAR" if mode == "Maghrib" else "🥣 SAHUR"
        mesaj = (
            f"✨ <b>{header} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b>  <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b>  <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"{bar} <b>%{int(progress*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"💠 <i>Hayırlı Ramazanlar.</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Hata: {e}")

# =========================
# 🛠️ ADMIN VE START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat(update.effective_chat.id, update.effective_chat.type)
    keyboard = [[InlineKeyboardButton("🌙 İftar", callback_data='btn_i'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_s')]]
    await update.message.reply_text(
        "⚜️ <b>RAMAZAN ELITE v20</b> ⚜️\n\n"
        "Şehir ismini Türkçe karakterlerle yazabilirsiniz.\n"
        "Örn: <code>/iftar Şanlıurfa</code>", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(f"📊 <b>Toplam Gönül Dostu:</b> <code>{len(load_chats())}</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    chats = load_chats()
    for c in chats:
        try: await context.bot.send_message(c["chat_id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
        except: pass

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'btn_i': await q.message.reply_text("🍽 <code>/iftar şehir</code> yazın.")
    if q.data == 'btn_s': await q.message.reply_text("🥣 <code>/sahur şehir</code> yazın.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat(u.effective_chat.id, u.effective_chat.type)))
    app.run_polling()

if __name__ == "__main__":
    main()
