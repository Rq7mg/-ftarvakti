import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE HAFIZA
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
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur."
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
    if chat_id not in [c.get("chat_id") for c in chats]:
        chats.append({"chat_id": chat_id})
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f)

# =========================
# 📡 İMSAKİYE MOTORU (30 GÜNLÜK)
# =========================
async def get_imsakiye_data(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    if city_clean in IMSAKIYE_CACHE: return IMSAKIYE_CACHE[city_clean]

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            url = f"https://api.aladhan.com/v1/calendarByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()["data"]
                IMSAKIYE_CACHE[city_clean] = data
                return data
        except: return None
    return None

# =========================
# 🎭 ANA HESAPLAMA (İFTAR & SAHUR)
# =========================
async def vakit_hesapla(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir yazın.\nÖrn: <code>/{mode} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("🔎 Veriler imsakiyeden çekiliyor...")
    imsakiye = await get_imsakiye_data(city)

    if not imsakiye:
        await status_msg.edit_text("❌ Şehir bulunamadı veya sunucu yanıt vermiyor.")
        return

    try:
        tz = pytz.timezone("Europe/Istanbul")
        now = datetime.now(tz)
        
        # Bugünün verisi (İndeks 0-29 arası)
        day_index = now.day - 1
        day_data = imsakiye[day_index]["timings"]
        
        # Sahur için 'Fajr' (İmsak), İftar için 'Maghrib' (Akşam)
        v_key = "Maghrib" if mode == "iftar" else "Fajr"
        v_saat = day_data[v_key].split(" ")[0]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        
        if now >= target: # Vakit geçtiyse yarına bak
            day_data = imsakiye[now.day]["timings"]
            v_saat = day_data[v_key].split(" ")[0]
            target += timedelta(days=1)
            target = target.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]))

        diff = int((target - now).total_seconds())
        bar = "🟦" * int(10 * (1 - diff/57600)) + "⬜" * (10 - int(10 * (1 - diff/57600)))

        res_text = (
            f"🌙 <b>{mode.upper()} VAKTİ | {city.upper()}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Saat:</b> <code>{v_saat}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
            f"📊 <b>İlerleme:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>"
        )
        await status_msg.edit_text(res_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text(f"❌ Hata: {str(e)}")

# =========================
# 🛠️ ADMIN PANELİ (STATS & DUYURU)
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    users = load_chats()
    await update.message.reply_text(f"📊 <b>Bot İstatistikleri</b>\n\n👤 Toplam Kullanıcı: {len(users)}\n⚡ Aktif Şehir Önbelleği: {len(IMSAKIYE_CACHE)}", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Kullanım: <code>/duyuru mesaj</code>", parse_mode=ParseMode.HTML)
        return
    
    users = load_chats()
    count = 0
    for u in users:
        try:
            await context.bot.send_message(u["chat_id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ Duyuru {count} kişiye başarıyla iletildi.")

# =========================
# 🎮 KOMUTLAR & BAŞLATICI
# =========================
async def start(u, c):
    save_chat(u.effective_chat.id)
    kb = [
        [InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
        [InlineKeyboardButton("📜 Hadis", callback_data='h')],
        [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]
    ]
    await u.message.reply_text("✨ <b>RAMAZAN VAKİT BOT v37</b> ✨\nHoş geldiniz! Şehir yazarak sorgulama yapabilirsiniz.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def callback_handler(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'i': await q.message.reply_text("📍 İftar sorgulamak için <code>/iftar şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif q.data == 's': await q.message.reply_text("📍 Sahur sorgulamak için <code>/sahur şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif q.data == 'h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    elif q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("💡 Duyuru göndermek için <code>/duyuru mesaj</code> yazın.", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: vakit_hesapla(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: vakit_hesapla(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("hadis", lambda u,c: u.message.reply_text(random.choice(HADISLER))))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat(u.effective_chat.id)))
    
    print("🚀 v37 SİSTEM BAŞLATILDI!")
    app.run_polling()

if __name__ == "__main__": main()
