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

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır."
]

# =========================
# 💾 KULLANICI YÖNETİMİ
# =========================
def save_user(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    try:
        with open(CHATS_FILE, "r+") as f:
            data = json.load(f)
            if chat_id not in [u.get("id") for u in data]:
                data.append({"id": chat_id})
                f.seek(0); json.dump(data, f); f.truncate()
    except Exception as e:
        logging.error(f"Dosya kayıt hatası: {e}")

# =========================
# 📡 CANLI VERİ MOTORU (DİYANET METODU)
# =========================
async def get_live_data(city_name):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    
    # Canlı API üzerinden her gün değişen vakitleri çeker
    url = f"https://api.aladhan.com/v1/timingsByCity?city={clean_city}&country=Turkey&method=13"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                d = res.json()["data"]
                return {
                    "imsak": d["timings"]["Fajr"],
                    "iftar": d["timings"]["Maghrib"],
                    "tarih": d["date"]["readable"],
                    "yer": city_name.upper()
                }
        except: return None
    return None

# =========================
# 🎭 ANA İŞLEM MOTORU
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir yazın.\nÖrn: <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    status = await update.message.reply_text("📡 <b>Güncel Diyanet verileri çekiliyor...</b>", parse_mode=ParseMode.HTML)
    data = await get_live_data(city)

    if not data:
        await status.edit_text("⚠️ Veri alınamadı. Şehir ismini (Mardin, Ankara vb.) doğru yazdığınızdan emin olun.")
        return

    v_saat = data["iftar"] if mode == "iftar" else data["imsak"]
    
    # Zaman Hesaplama
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    
    if now >= target: target += timedelta(days=1)
    diff = int((target - now).total_seconds())
    
    bar_count = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🟦" * bar_count + "⬜" * (10 - bar_count)

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
        f"📅 Tarih: <code>{data['tarih']}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Vakit: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
        f"📊 Günlük İlerleme:\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>{random.choice(HADISLER)}</i>"
    )
    await status.edit_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN PANELİ & KOMUTLAR
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [
        [InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
        [InlineKeyboardButton("📊 İstatistik", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]
    ]
    await u.message.reply_text(
        "✨ <b>RAMAZAN CANLI v70</b> ✨\n\nHoş geldiniz! Botumuz her sorguda canlı Diyanet verilerini çeker. "
        "Böylece her gün değişen saatleri tam vaktinde öğrenirsiniz.", 
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
    )

async def stats(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    try:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
    except: count = 0
    await (u.message.reply_text if u.message else u.callback_query.message.reply_text)(f"📊 <b>BOT İSTATİSTİĞİ</b>\n\n👤 Toplam Kullanıcı: {count}", parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    txt = " ".join(c.args)
    if not txt:
        await u.message.reply_text("❌ Kullanım: <code>/duyuru Mesajınız</code>", parse_mode=ParseMode.HTML)
        return
    
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    sent, fail = 0, 0
    for user in users:
        try:
            await c.bot.send_message(user["id"], f"📢 <b>DUYURU</b>\n\n{txt}", parse_mode=ParseMode.HTML)
            sent += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await u.message.reply_text(f"✅ Duyuru bitti.\nBaşarılı: {sent}\nHatalı: {fail}")

async def button_handler(u, c):
    q = u.callback_query; await q.answer()
    if q.data == 'i': await q.message.reply_text("📍 İftar için: <code>/iftar Şehir</code>", parse_mode=ParseMode.HTML)
    elif q.data == 's': await q.message.reply_text("📍 Sahur için: <code>/sahur Şehir</code>", parse_mode=ParseMode.HTML)
    elif q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("📢 Duyuru göndermek için <code>/duyuru mesaj</code> yazın.", parse_mode=ParseMode.HTML)

# =========================
# ⚙️ ÇALIŞTIRICI
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🚀 Bot v70 Canlı Modda Başlatıldı!")
    app.run_polling()

if __name__ == "__main__": main()
