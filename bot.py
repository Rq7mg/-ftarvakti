import os, json, httpx, pytz, random, logging, asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR (Burayı Doldur)
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN")  # Botunuzun tokeni
ADMIN_IDS = [6563936773, 6030484208] # Admin ID'leri
CHATS_FILE = "chats.json" # Kullanıcı listesi

# GITHUB'A YÜKLEDİĞİN JSON LİNKİNİ BURAYA YAZ
# Örn: "https://raw.githubusercontent.com/kullanici/depo/main/vakitler.json"
JSON_URL = "https://raw.githubusercontent.com/KULLANICI/DEPO/main/vakitler.json"

# 2026 Ramazan Başlangıcı
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=pytz.timezone("Europe/Istanbul"))

# Global Hafıza
LOCAL_CACHE = {}
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Oruçlu için iki sevinç vardır: İftar ve Rabbine kavuştuğu an. ✨"
]

# =========================
# 💾 VERİ VE KULLANICI YÖNETİMİ
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
    except: pass

async def sync_data():
    global LOCAL_CACHE
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.get(JSON_URL)
            if res.status_code == 200:
                LOCAL_CACHE = res.json()
                print("✅ Vakit verileri hafızaya alındı!")
                return True
        except Exception as e:
            print(f"❌ Veri senkronizasyon hatası: {e}")
            # Eğer JSON yoksa botun çökmemesi için basit bir boş yapı kur
            LOCAL_CACHE = {}
    return False

# =========================
# 🎭 ANA MOTOR (İFTAR/SAHUR)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    save_user(update.effective_chat.id)
    
    city_raw = " ".join(context.args).lower().strip() if context.args else None
    if not city_raw:
        await update.message.reply_text(f"📍 <b>Hatalı kullanım!</b>\nÖrnek: <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    # Türkçe karakter temizleme
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city = city_raw.translate(tr_map)

    if city not in LOCAL_CACHE:
        await update.message.reply_text("❌ <b>Şehir Bulunamadı!</b>\nJSON dosyanızda bu şehir tanımlı değil.")
        return

    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    
    # Ramazan Günü Hesapla
    r_day = (now.date() - RAMAZAN_START.date()).days + 1
    
    if r_day < 1 or r_day > 30:
        await update.message.reply_text("🌙 Şu an Ramazan ayı içerisinde değiliz.")
        return

    try:
        v_saat = LOCAL_CACHE[city][mode][r_day-1]
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        # Görsel İlerleme Barı
        p = min(10, max(0, int(10 * (1 - diff/57600))))
        bar = "🟦" * p + "⬜" * (10 - p)

        msg = (
            f"🌙 <b>{mode.upper()} VAKTİ | {city_raw.upper()}</b>\n"
            f"📅 <b>Ramazan'ın {r_day}. Günü</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Saat: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <b>{diff//3600}sa {(diff%3600)//60}dk</b>\n\n"
            f"📊 <b>Vakte Kalan Süre:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📢 <i>{random.choice(HADISLER)}</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text("❌ Veri işleme hatası oluştu.")

# =========================
# 🛠 ADMİN KOMUTLARI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    msg = (
        "✨ <b>Ramazan Asistanı v160</b> ✨\n\n"
        "Şehrinizdeki iftar ve sahur vakitlerini saniyesi saniyesine öğrenebilirsiniz.\n\n"
        "📍 <b>Komutlar:</b>\n"
        "/iftar [şehir] - İftar vaktini gösterir\n"
        "/sahur [şehir] - Sahur vaktini gösterir\n"
        "/yardim - Detaylı bilgi verir"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
        await update.message.reply_text(f"👤 <b>Toplam Kullanıcı:</b> {count}", parse_mode=ParseMode.HTML)
    except: await update.message.reply_text("❌ Veri okunamadı.")

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Kullanım: /duyuru [mesaj]")
        return
    
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    success, fail = 0, 0
    for user in users:
        try:
            await context.bot.send_message(user["id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            success += 1
        except: fail += 1
    await update.message.reply_text(f"✅ Bitti!\nBaşarılı: {success}\nBaşarısız: {fail}")

# =========================
# 🏁 KURULUM
# =========================
async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Bot açılırken verileri bir kez çek
    await sync_data()

    # Handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    print("🚀 Bot v160 Kesintisiz Olarak Başlatıldı!")
    await app.updater.initialize()
    await app.updater.start_polling()
    await app.initialize()
    await app.start()
    
    # Botu hayatta tut
    while True: await asyncio.sleep(1000)

if __name__ == "__main__":
    asyncio.run(run_bot())
