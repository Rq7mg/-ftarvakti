import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR
# =========================
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu vakit.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur.",
    "Oruç, cehennem ateşinden koruyan bir kalkandır."
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_chat(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🚀 ÇİFT MOTORLU API SİSTEMİ
# =========================
async def get_times(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    async with httpx.AsyncClient() as client:
        # 1. DENEME: Ana API (Aladhan)
        try:
            url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url, timeout=7)
            if res.status_code == 200:
                d = res.json()["data"]
                return {"v": d["timings"], "tz": d["meta"]["timezone"], "yer": city_input.upper()}
        except: pass

        # 2. DENEME: Yedek API (Eğer ilki çökerse buraya geçer)
        try:
            url2 = f"https://dailyprayer.abdulrcs.repl.co/api/turkey/{city_clean}"
            res2 = await client.get(url2, timeout=5)
            if res2.status_code == 200:
                d2 = res2.json()
                # API format dönüşümü
                return {"v": {"Fajr": d2["fajr"], "Maghrib": d2["maghrib"]}, "tz": "Europe/Istanbul", "yer": city_input.upper()}
        except: pass
    return None

# =========================
# 🎭 ANA KOMUTLAR
# =========================
async def vakit_motoru(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text("📍 Örn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)
        return

    data = await get_times(city)
    if not data:
        await update.message.reply_text("⚠️ Sunucu şu an yoğun veya şehir bulunamadı. Lütfen az sonra tekrar deneyin.")
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        vakit_saat = data["v"][mode]
        target = now.replace(hour=int(vakit_saat.split(":")[0]), minute=int(vakit_saat.split(":")[1]), second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        # Görsel Bar
        p = min(1, max(0, 1 - (diff / 57600)))
        bar = "🌕" * int(10 * p) + "🌑" * (10 - int(10 * p))

        baslik = "🌙 İFTAR" if mode == "Maghrib" else "🥣 SAHUR"
        mesaj = (
            f"✨ <b>{baslik} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{vakit_saat}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{diff//3600}s {(diff%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(p*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📜 <i>{random.choice(HADISLER)}</i>"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=mesaj, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ Bir hata oluştu.")

# =========================
# 🛠️ ADMIN & FONKSİYONLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat.id)
    kb = [[InlineKeyboardButton("🌙 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📜 Hadis", callback_data='h')]]
    await update.message.reply_text("⚜️ <b>RAMAZAN v26</b> ⚜️\nHoş geldiniz.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def hadis_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(context.args)
    chats = load_chats()
    for c in chats:
        try: await context.bot.send_message(c["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML); await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Gönderildi.")

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    else: await q.message.reply_text("🍽 Lütfen <code>/iftar Şehir</code> yazın.", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: vakit_motoru(u,c,"Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u,c: vakit_motoru(u,c,"Fajr")))
    app.add_handler(CommandHandler("hadis", hadis_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat(u.effective_chat.id)))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
