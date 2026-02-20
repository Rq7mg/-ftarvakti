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
CACHE = {} 

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def save_chat(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    with open(CHATS_FILE, "r+") as f:
        data = json.load(f)
        if chat_id not in [c.get("chat_id") for c in data]:
            data.append({"chat_id": chat_id})
            f.seek(0); json.dump(data, f); f.truncate()

# =========================
# 📡 YENİ NESİL VERİ ÇEKİCİ (STABIL)
# =========================
async def get_times(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    if city_clean in CACHE:
        exp, data = CACHE[city_clean]
        if datetime.now() < exp: return data

    # Türkiye için en hızlı ve bloklanmayan API rotası
    # Eğer Aladhan bloklarsa bu alternatif devreye girer
    urls = [
        f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13",
        f"https://islampreyr.com/api/times?city={city_clean}" # Yedek hat
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in urls:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    d = res.json()["data"]["timings"]
                    res_obj = {"v": d, "yer": city_input.upper()}
                    CACHE[city_clean] = (datetime.now() + timedelta(hours=6), res_obj)
                    return res_obj
            except: continue
    return None

# =========================
# 🎭 VAKİT MOTORU (ASENKRON)
# =========================
async def iftar_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await engine(u, c, "Maghrib", "İFTAR")

async def sahur_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await engine(u, c, "Fajr", "SAHUR")

async def engine(u: Update, c: ContextTypes.DEFAULT_TYPE, key, label):
    city = " ".join(c.args) if c.args else None
    if not city:
        await u.message.reply_text(f"📍 Şehir yazın. Örn: <code>/{label.lower()} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    tmp = await u.message.reply_text("📡 Veritabanına bağlanılıyor...")
    data = await get_times(city)

    if not data:
        await tmp.edit_text("❌ <b>Hata:</b> Sunucular şu an meşgul. Lütfen 1 dakika sonra tekrar deneyin.")
        return

    try:
        tz = pytz.timezone("Europe/Istanbul")
        now = datetime.now(tz)
        v_saat = data["v"][key]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        bar = "🟦" * int(10 * (1 - diff/57600)) + "⬜" * (10 - int(10 * (1 - diff/57600)))
        
        await tmp.edit_text(
            f"🌙 <b>{label} VAKTİ | {data['yer']}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Saat: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
            f"{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>",
            parse_mode=ParseMode.HTML
        )
    except: await tmp.edit_text("⚠️ Hesaplama hatası oluştu.")

# =========================
# 🛠️ ADMIN & START
# =========================
async def start(u, c):
    save_chat(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]]
    await u.message.reply_text("✨ <b>RAMAZAN NITRO v40</b> ✨\nHoş geldiniz! Hızlı sorgu için şehir yazın.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def stats(u, c):
    if u.effective_user.id in ADMIN_IDS:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
        await u.message.reply_text(f"📊 Toplam Kullanıcı: {count}")

async def duyuru(u, c):
    if u.effective_user.id in ADMIN_IDS:
        msg = " ".join(c.args)
        if not msg: return
        with open(CHATS_FILE, "r") as f: users = json.load(f)
        for user in users:
            try: await c.bot.send_message(user["chat_id"], f"📢 {msg}")
            except: pass
        await u.message.reply_text("✅ Duyuru bitti.")

async def cb(u, c):
    q = u.callback_query; await q.answer()
    if q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("Duyuru için: /duyuru mesaj")
    else: await q.message.reply_text("📍 Örn: /iftar istanbul")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb))
    app.run_polling()

if __name__ == "__main__": main()
