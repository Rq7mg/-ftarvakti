import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"
IMSAKIYE_CACHE = {} 

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_chat(chat_id):
    chats = load_chats()
    if not any(c.get("chat_id") == chat_id for c in chats):
        chats.append({"chat_id": chat_id})
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f)

# =========================
# 📡 İMSAKİYE MOTORU (ÇÖKME KORUMALI)
# =========================
async def get_imsakiye(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    if city_clean in IMSAKIYE_CACHE: return IMSAKIYE_CACHE[city_clean]

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            url = f"https://api.aladhan.com/v1/calendarByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()["data"]
                IMSAKIYE_CACHE[city_clean] = data
                return data
        except Exception as e:
            logging.error(f"API Hatası: {e}")
            return None
    return None

# =========================
# 🎭 VAKİT İŞLEYİCİLER (LOGDAKİ HATAYI ÇÖZER)
# =========================
async def iftar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_hesapla(update, context, "Maghrib", "İFTAR")

async def sahur_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_hesapla(update, context, "Fajr", "SAHUR")

async def vakit_hesapla(update: Update, context: ContextTypes.DEFAULT_TYPE, key, label):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir yazın.\nÖrn: <code>/{label.lower()} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    status = await update.message.reply_text(f"⏳ {city.upper()} için veriler çekiliyor...")
    data = await get_imsakiye(city)

    if not data:
        await status.edit_text("⚠️ Veri şu an alınamadı. Şehir ismini kontrol edin veya az sonra tekrar deneyin.")
        return

    try:
        tz = pytz.timezone("Europe/Istanbul")
        now = datetime.now(tz)
        # Mevcut günün verisini al
        day_data = data[now.day - 1]["timings"]
        v_saat = day_data[key].split(" ")[0]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        
        if now >= target: # Vakit geçtiyse yarının verisine bak
            day_data = data[now.day]["timings"]
            v_saat = day_data[key].split(" ")[0]
            target = (target + timedelta(days=1)).replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]))

        diff = int((target - now).total_seconds())
        bar = "🟦" * int(10 * (1 - diff/57600)) + "⬜" * (10 - int(10 * (1 - diff/57600)))

        msg = (
            f"🌙 <b>{label} VAKTİ | {city.upper()}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Vakit: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <code>{diff//3600} saat {(diff%3600)//60} dk</code>\n\n"
            f"{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>"
        )
        await status.edit_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Hesaplama hatası: {e}")
        await status.edit_text("❌ Vakit hesaplanırken bir sorun oluştu.")

# =========================
# 🛠️ ADMIN KOMUTLARI
# =========================
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    users = load_chats()
    await update.message.reply_text(f"📊 <b>BOT STATS</b>\n\n👤 Toplam Kullanıcı: {len(users)}\n💾 Önbellek: {len(IMSAKIYE_CACHE)} şehir", parse_mode=ParseMode.HTML)

async def duyuru_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Kullanım: <code>/duyuru Mesaj</code>", parse_mode=ParseMode.HTML)
        return
    
    users = load_chats()
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u["chat_id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ Duyuru {sent} kişiye iletildi.")

# =========================
# 🎮 ANA MENÜ VE BAŞLATICI
# =========================
async def start(u, c):
    save_chat(u.effective_chat.id)
    kb = [
        [InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
        [InlineKeyboardButton("📜 Hadis", callback_data='h')],
        [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]
    ]
    await u.message.reply_text("✨ <b>RAMAZAN VAKİT BOT v39</b> ✨\nLütfen yapmak istediğiniz işlemi seçin veya şehir yazın.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def handle_cb(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'i': await q.message.reply_text("📍 İftar için: <code>/iftar şehir</code>", parse_mode=ParseMode.HTML)
    elif q.data == 's': await q.message.reply_text("📍 Sahur için: <code>/sahur şehir</code>", parse_mode=ParseMode.HTML)
    elif q.data == 'h': await q.message.reply_text(f"📜 {random.choice(HADISLER)}")
    elif q.data == 'st': await stats_cmd(u, c)
    elif q.data == 'dy': await q.message.reply_text("💡 Duyuru için <code>/duyuru</code> komutunu kullanın.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru_cmd))
    app.add_handler(CallbackQueryHandler(handle_cb))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat(u.effective_chat.id)))
    
    print("🚀 Bot v39 Yayında!")
    app.run_polling()

if __name__ == "__main__": main()
