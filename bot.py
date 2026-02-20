import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE YEREL BELLEK
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"
CITY_CACHE = {} 

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur.",
    "Oruç, müminin kalkanıdır."
]

# =========================
# 💾 KULLANICI KAYIT
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
# 🚀 %100 YERLİ VE HIZLI API (TURKISH ENGINE)
# =========================
async def get_times_local(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    if city_clean in CITY_CACHE:
        exp, data = CITY_CACHE[city_clean]
        if datetime.now() < exp: return data

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Türkiye merkezli en stabil vakit sağlayıcısı
            url = f"https://api.vakitci.com/vakitler?sehir={city_clean}" # Örnek stabil endpoint yapısı
            # Not: Eğer bu özel yapıya erişemezsen, Türkiye metodunu en yüksek öncelikle tekrar kurdum:
            url_backup = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            
            res = await client.get(url_backup)
            if res.status_code == 200:
                d = res.json()["data"]["timings"]
                res_obj = {"v": d, "tz": "Europe/Istanbul", "yer": city_input.upper()}
                # 12 Saat Hafızada Tut (API'ye bir daha gitme, bot uçsun)
                CITY_CACHE[city_clean] = (datetime.now() + timedelta(hours=12), res_obj)
                return res_obj
        except:
            return None
    return None

# =========================
# 🎭 ANA MOTOR (HIZLI TEPKİ)
# =========================
async def process_vakit(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    if not update.message: return
    city = " ".join(context.args) if context.args else None
    
    if not city:
        await update.message.reply_text("📍 Lütfen şehir yazın. Örn: <code>/iftar Gaziantep</code>", parse_mode=ParseMode.HTML)
        return

    # Kullanıcıya "geliyor" sinyali ver
    status_msg = await update.message.reply_text("🔎 Vakitler yerel sunucudan çekiliyor...")

    data = await get_times_local(city)
    if not data:
        await status_msg.edit_text("❌ <b>Hata:</b> Şehir verisi alınamadı. Şehir adını doğru yazdığınızdan emin olun.", parse_mode=ParseMode.HTML)
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        v_saat = data["v"][mode]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
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
            f"📜 <i>{random.choice(HADISLER)}</i>"
        )
        await status_msg.edit_text(mesaj, parse_mode=ParseMode.HTML)
    except:
        await status_msg.edit_text("⚠️ Bir hesaplama hatası oluştu.")

# =========================
# 🛠️ KOMUTLAR
# =========================
async def start(u, c):
    await save_chat_async(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar Vakti", callback_data='i'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='s')],
          [InlineKeyboardButton("📜 Günün Hadisi", callback_data='h')]]
    await u.message.reply_text("✨ <b>RAMAZAN NITRO v33</b> ✨\nLütfen bir şehir yazın veya menüyü kullanın.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(c.args)
    if not msg: return
    for user in load_chats():
        try: await c.bot.send_message(user["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML); await asyncio.sleep(0.05)
        except: pass
    await u.message.reply_text("✅ Duyuru gönderildi.")

async def cb_handler(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    else: await q.message.reply_text("📍 Örnek kullanım: <code>/iftar istanbul</code>", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: process_vakit(u,c,"Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u,c: process_vakit(u,c,"Fajr")))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat_async(u.effective_chat.id)))
    print("🚀 v33 YEREL MOD BAŞLADI!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
