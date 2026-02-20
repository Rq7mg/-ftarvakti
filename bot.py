import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR & HIZLANDIRICI (CACHE)
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"
CACHE = {} # Sorguları hafızada tutarak hızı artırır

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
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat_async(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🚀 YEDEKLİ VE HIZLI API MOTORU
# =========================
async def get_times_turbo(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    # 1. Cache Kontrolü (Süper Hız)
    if city_clean in CACHE:
        expire, data = CACHE[city_clean]
        if datetime.now() < expire: return data

    async with httpx.AsyncClient() as client:
        # 1. KAYNAK (Aladhan)
        try:
            url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url, timeout=5)
            if res.status_code == 200:
                d = res.json()["data"]
                result = {"v": d["timings"], "tz": d["meta"]["timezone"], "yer": city_input.upper()}
                CACHE[city_clean] = (datetime.now() + timedelta(hours=2), result) # 2 saat cache
                return result
        except: pass

        # 2. KAYNAK (Yedek - PrayTimes)
        try:
            url2 = f"https://api.pray.zone/v2/times/today.json?city={city_clean}"
            res2 = await client.get(url2, timeout=5)
            if res2.status_code == 200:
                d2 = res2.json()["results"]["datetime"][0]["times"]
                tz2 = res2.json()["results"]["location"]["timezone"]
                result = {"v": {"Fajr": d2["Fajr"], "Maghrib": d2["Maghrib"]}, "tz": tz2, "yer": city_input.upper()}
                CACHE[city_clean] = (datetime.now() + timedelta(hours=2), result)
                return result
        except: pass
    return None

# =========================
# 🎭 ANA KOMUTLAR
# =========================
async def vakit_isleyici(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    if not update.message: return
    city = " ".join(context.args) if context.args else None
    
    if not city:
        await update.message.reply_text("📍 Örn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)
        return

    data = await get_times_turbo(city)
    if not data:
        await update.message.reply_text("⚠️ Şehir bulunamadı veya sunucular yoğun. Lütfen tekrar deneyin.")
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        v_saat = data["v"][mode]
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        p = min(1, max(0, 1 - (diff / 57600)))
        bar = "🌕" * int(10 * p) + "🌑" * (10 - int(10 * p))
        baslik = "🌙 İFTAR" if mode == "Maghrib" else "🥣 SAHUR"
        
        mesaj = (
            f"✨ <b>{baslik} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{v_saat}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{diff//3600}s {(diff%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(p*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📜 <i>{random.choice(HADISLER)}</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ Hesaplama hatası.")

# =========================
# 🛠️ DİĞER KOMUTLAR (ASENKRON)
# =========================
async def iftar_cmd(u, c): await vakit_isleyici(u, c, "Maghrib")
async def sahur_cmd(u, c): await vakit_isleyici(u, c, "Fajr")

async def start(u, c):
    await save_chat_async(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🌙 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📜 Hadis", callback_data='h')]]
    await u.message.reply_text("⚜️ <b>RAMAZAN NITRO v28</b> ⚜️\nSorgu için şehir yazın.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(c.args)
    for ch in load_chats():
        try: await c.bot.send_message(ch["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML); await asyncio.sleep(0.04)
        except: pass
    await u.message.reply_text("✅ Tamamlandı.")

async def cb_worker(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    else: await q.message.reply_text("🍽 <code>/iftar şehir</code> yazın.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb_worker))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat_async(u.effective_chat.id)))
    print("🚀 v28 NITRO BAŞLADI!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
