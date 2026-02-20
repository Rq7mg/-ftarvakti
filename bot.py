import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE TÜRKİYE MERKEZLİ CACHE
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"
# Hafıza (Cache): Şehir verilerini 12 saat tutar, API'ye gitmez.
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
# 💾 KULLANICI YÖNETİMİ
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
# 🚀 TÜRKİYE ODAKLI API (TEK KAYNAK - STABİL)
# =========================
async def get_times_local(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "")
    
    # 1. HIZ İÇİN CACHE KONTROLÜ
    if city_clean in CITY_CACHE:
        exp, data = CITY_CACHE[city_clean]
        if datetime.now() < exp: return data

    # 2. TÜRKİYE VERİSİ İÇİN EN STABİL KAYNAK (Proxy üzerinden)
    async with httpx.AsyncClient() as client:
        try:
            # Türkiye sunucularına en yakın ve en hızlı çalışan endpoint
            url = f"https://api.collectapi.com/pray/all?data.city={city_clean}"
            headers = {
                "content-type": "application/json",
                "authorization": "apikey 3N09YV6C4N8V8V:5L8V8V8V8V8V8V" # Örnek Key: Kendi keyini buraya koymalısın
            }
            # Not: CollectAPI veya yerel bir scrape servisi Türkiye'de en hızlısıdır. 
            # Senin için en hızlı ve ücretsiz kalacak olan Aladhan'ın Türkiye Method 13 (Diyanet) ayarını 
            # timeout'u optimize ederek tek kaynak olarak sabitliyorum:
            
            url_fix = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url_fix, timeout=5)
            
            if res.status_code == 200:
                d = res.json()["data"]
                res_obj = {
                    "v": d["timings"], 
                    "tz": "Europe/Istanbul", 
                    "yer": city_input.upper()
                }
                # 12 Saat Boyunca Bu Şehri Bir Daha Sorgulama (Müthiş Hız Sağlar)
                CITY_CACHE[city_clean] = (datetime.now() + timedelta(hours=12), res_obj)
                return res_obj
        except:
            return None
    return None

# =========================
# 🎭 ANA MOTOR (HATA KORUMALI)
# =========================
async def process_vakit(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    if not update.message: return
    
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text("📍 Lütfen bir şehir adı girin.\nÖrn: <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)
        return

    # API Sorgusu
    data = await get_times_local(city)
    
    if not data:
        await update.message.reply_text("⚠️ Veri şu an alınamadı. Lütfen şehir adını kontrol edin veya az sonra tekrar deneyin.")
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        v_saat = data["v"][mode]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0, microsecond=0)
        
        if now >= target: 
            target += timedelta(days=1)
            
        diff = int((target - now).total_seconds())
        
        # Görsel Tasarım
        p = min(1, max(0, 1 - (diff / 57600)))
        bar = "🌕" * int(10 * p) + "🌑" * (10 - int(10 * p))
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
    except Exception as e:
        logging.error(f"Hata: {e}")
        await update.message.reply_text("❌ Vakit hesaplanırken bir sorun oluştu.")

# =========================
# 🛠️ KOMUT YÖNLENDİRMELERİ (LAMBDA YOK)
# =========================
async def iftar_cmd(u, c): await process_vakit(u, c, "Maghrib")
async def sahur_cmd(u, c): await process_vakit(u, c, "Fajr")

async def start(u, c):
    await save_chat_async(u.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar Vakti", callback_data='i'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='s')],
        [InlineKeyboardButton("📜 Günün Hadisi", callback_data='h')]
    ]
    await u.message.reply_text("✨ <b>RAMAZAN VAKİT BOT v30</b> ✨\nHoş geldiniz. Şehir yazarak sorgu yapabilirsiniz.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def duyuru_cmd(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(c.args)
    if not msg: return
    count = 0
    for user in load_chats():
        try: 
            await c.bot.send_message(user["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await u.message.reply_text(f"✅ {count} kişiye duyuru iletildi.")

async def cb_handler(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h':
        await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    else:
        await q.message.reply_text("📍 Lütfen <code>/iftar şehir</code> şeklinde yazın.", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru_cmd))
    app.add_handler(CallbackQueryHandler(cb_handler))
    
    # Kullanıcı Kaydı (Her mesajda)
    async def track(u, c): 
        if u.effective_chat: await save_chat_async(u.effective_chat.id)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track))
    
    print("🚀 v30 YEREL HIZ MODU AKTİF!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
