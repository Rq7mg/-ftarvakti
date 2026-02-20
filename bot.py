import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE HIZLI CACHE
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
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur.",
    "Allah'ım! Sen affedicisin, affetmeyi seversin, beni de affet."
]

# =========================
# 💾 VERİ TABANI (HIZLI)
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat_async(chat_id):
    chats = load_chats()
    if not any(c['chat_id'] == chat_id for c in chats):
        chats.append({"chat_id": chat_id})
        with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)

# =========================
# 🚀 ULTRA HIZLI YEDEKLİ API
# =========================
async def get_times_ultimate(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    # Cache Kontrolü
    if city_clean in CACHE:
        exp, data = CACHE[city_clean]
        if datetime.now() < exp: return data

    async with httpx.AsyncClient() as client:
        # 1. Kaynak (Hızlı Sorgu)
        try:
            res = await client.get(f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13", timeout=4)
            if res.status_code == 200:
                d = res.json()["data"]
                res_obj = {"v": d["timings"], "tz": d["meta"]["timezone"], "yer": city_input.upper()}
                CACHE[city_clean] = (datetime.now() + timedelta(hours=3), res_obj)
                return res_obj
        except: pass

        # 2. Kaynak (Yedek - Hata Durumunda)
        try:
            res2 = await client.get(f"https://api.pray.zone/v2/times/today.json?city={city_clean}", timeout=4)
            if res2.status_code == 200:
                d2 = res2.json()["results"]["datetime"][0]["times"]
                tz2 = res2.json()["results"]["location"]["timezone"]
                res_obj = {"v": {"Fajr": d2["Fajr"], "Maghrib": d2["Maghrib"]}, "tz": tz2, "yer": city_input.upper()}
                CACHE[city_clean] = (datetime.now() + timedelta(hours=3), res_obj)
                return res_obj
        except: pass
    return None

# =========================
# 🎭 MOTOR (GÖRSEL ODAKLI)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    if not update.message: return
    city = " ".join(context.args) if context.args else None
    
    if not city:
        await update.message.reply_text("📍 Lütfen bir şehir adı girin.\nÖrn: <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)
        return

    data = await get_times_ultimate(city)
    if not data:
        await update.message.reply_text("⚠️ <b>Şehir bulunamadı</b> veya sunucular şu an yanıt vermiyor. Lütfen tekrar deneyin.", parse_mode=ParseMode.HTML)
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        v_saat = data["v"][mode]
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        # İlerleme Barı (Görseldeki gibi)
        p = min(1, max(0, 1 - (diff / 57600)))
        bar = "🔵" * int(10 * p) + "⚪" * (10 - int(10 * p))
        label = "İFTARA" if mode == "Maghrib" else "SAHURA"

        mesaj = (
            f"✨ <b>{label} NE KADAR KALDI?</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📍 <b>Bölge:</b> {data['yer']}\n"
            f"⏰ <b>Vakit:</b> {v_saat}\n"
            f"⏳ <b>Kalan:</b> {diff//3600} saat {(diff%3600)//60} dk\n\n"
            f"<b>Doluluk:</b> {bar} %{int(p*100)}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ Hesaplama sırasında bir hata oluştu.")

# =========================
# 🛠️ ADMIN & KOMUTLAR
# =========================
async def iftar_cmd(u, c): await engine(u, c, "Maghrib")
async def sahur_cmd(u, c): await engine(u, c, "Fajr")

async def start(u, c):
    await save_chat_async(u.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar Vakti", callback_data='i'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='s')],
        [InlineKeyboardButton("📜 Hadis-i Şerif", callback_data='h'), InlineKeyboardButton("📢 Duyuru Yap", callback_data='d')]
    ]
    await u.message.reply_text("✨ <b>RAMAZAN VAKİT BOT</b> ✨\nLütfen yapmak istediğiniz işlemi seçin veya şehir yazın.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(c.args)
    if not msg: return
    for user in load_chats():
        try: await c.bot.send_message(user["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML); await asyncio.sleep(0.05)
        except: pass
    await u.message.reply_text("✅ Duyuru tüm kullanıcılara iletildi.")

async def cb_handler(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 <b>Hadis-i Şerif:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    elif q.data == 'd': await q.message.reply_text("💡 Duyuru yapmak için: <code>/duyuru mesajınız</code>", parse_mode=ParseMode.HTML)
    else: await q.message.reply_text("📍 Lütfen <code>/iftar şehir</code> yazarak sorgulama yapın.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("hadis", lambda u,c: u.message.reply_text(random.choice(HADISLER))))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat_async(u.effective_chat.id)))
    print("🚀 RAMAZAN VAKİT BOT AKTİF!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__": main()
