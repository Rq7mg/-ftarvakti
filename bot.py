import os, json, httpx, pytz, random, logging, asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ⚙️ AYARLAR VE LOGGING
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN")
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# GITHUB LİNKİN (Cache buster destekli)
JSON_URL = "https://raw.githubusercontent.com/Rq7mg/-ftarvakti/main/vakitler.json"

# 2026 Ramazan Başlangıcı
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=pytz.timezone("Europe/Istanbul"))

# Global Değişkenler
LOCAL_CACHE = {}
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Oruçlu için iki sevinç vardır: İftar ve Rabbine kavuştuğu an. ✨",
    "Kim inanarak ve sevabını Allah'tan bekleyerek Ramazan orucunu tutarsa, geçmiş günahları bağışlanır. ✨",
    "Cennette 'Reyyân' denilen bir kapı vardır ki, kıyamet günü oradan ancak oruçlular girer. ✨"
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def get_users():
    if not os.path.exists(CHATS_FILE): return []
    try:
        with open(CHATS_FILE, "r") as f: return json.load(f)
    except: return []

def save_user(chat_id):
    users = get_users()
    if not any(u.get("id") == chat_id for u in users):
        users.append({"id": chat_id})
        with open(CHATS_FILE, "w") as f: json.dump(users, f)

async def sync_data():
    """GitHub'dan verileri tazeleyerek çeker."""
    global LOCAL_CACHE
    url = f"{JSON_URL}?t={random.randint(1, 99999)}" # GitHub cache engelleme
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                LOCAL_CACHE = res.json()
                logger.info(f"✅ Vakitler yüklendi! Şehir sayısı: {len(LOCAL_CACHE)}")
                return True
            else:
                logger.error(f"❌ JSON hatası: {res.status_code}")
        except Exception as e:
            logger.error(f"❌ Bağlantı hatası: {e}")
    return False

def format_city_name(name):
    """Kullanıcı girişini JSON key formatına çevirir."""
    if not name: return ""
    name = name.lower().strip()
    # Türkçe karakterleri manuel temizleme (En güvenli yol)
    duzeltmeler = {
        "ç": "c", "ğ": "g", "ı": "i", "i̇": "i", "ö": "o", "ş": "s", "ü": "u",
        "İ": "i", "Ş": "s", "Ğ": "g", "Ü": "u", "Ö": "o", "Ç": "c"
    }
    for harf, yeni_harf in duzeltmeler.items():
        name = name.replace(harf, yeni_harf)
    return name

# =========================
# 🎭 ANA MOTOR (İFTAR/SAHUR)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    save_user(update.effective_chat.id)
    
    city_input = " ".join(context.args)
    city_key = format_city_name(city_input)

    if not city_key:
        await update.message.reply_text(f"📍 <b>Hatalı kullanım!</b>\nÖrnek: <code>/{mode} İstanbul</code>", parse_mode=ParseMode.HTML)
        return

    if not LOCAL_CACHE: 
        await sync_data()

    if city_key not in LOCAL_CACHE:
        # Hata mesajını detaylandırdık ki nerede sorun olduğunu anlayalım
        await update.message.reply_text(
            f"❌ <b>Şehir Bulunamadı!</b>\n\nSistemde <code>{len(LOCAL_CACHE)}</code> şehir yüklü.\n"
            f"Girdiğiniz: <code>{city_input}</code>\n"
            f"Aranan Anahtar: <code>{city_key}</code>\n\n"
            "Lütfen şehir ismini doğru yazdığınızdan emin olun.",
            parse_mode=ParseMode.HTML
        )
        return

    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    r_day = (now.date() - RAMAZAN_START.date()).days + 1
    
    if r_day < 1 or r_day > 30:
        await update.message.reply_text("🌙 2026 Ramazan ayı takvimine şu an ulaşılamıyor (Ramazan dışında mıyız?).")
        return

    try:
        v_saat = LOCAL_CACHE[city_key][mode][r_day-1]
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        
        diff_sec = int((target - now).total_seconds())
        
        if diff_sec < 0:
            msg_kalan = "Vakit geçti."
            bar = "🟦" * 10
        else:
            hours, remainder = divmod(diff_sec, 3600)
            minutes, _ = divmod(remainder, 60)
            msg_kalan = f"<b>{hours}sa {minutes}dk</b>"
            p = min(10, max(0, int(10 * (1 - diff_sec/57600))))
            bar = "🟦" * p + "⬜" * (10 - p)

        msg = (
            f"🌙 <b>{mode.upper()} VAKTİ | {city_input.upper()}</b>\n"
            f"📅 <b>Ramazan'ın {r_day}. Günü</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Saat: <code>{v_saat}</code>\n"
            f"⏳ Kalan: {msg_kalan}\n\n"
            f"📊 <b>Vakte İlerleme:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📢 <i>{random.choice(HADISLER)}</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Hesaplama hatası: {e}")
        await update.message.reply_text("❌ Vakit bilgisi getirilirken bir hata oluştu.")

# =========================
# 🛠 KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    await update.message.reply_text(
        "✨ <b>Ramazan Asistanı 2026</b> ✨\n\n"
        "📍 <b>Komutlar:</b>\n"
        "/iftar [şehir] - İftar vaktini gösterir\n"
        "/sahur [şehir] - Sahur vaktini gösterir\n"
        "/hadis - Rastgele bir hadis gönderir\n"
        "/yardim - Bu menüyü açar",
        parse_mode=ParseMode.HTML
    )

async def hadis_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <b>Günün Hadisi:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    count = len(get_users())
    await update.message.reply_text(f"👤 <b>Toplam Kullanıcı:</b> {count}", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Kullanım: /duyuru [mesaj]")
        return
    
    users = get_users()
    s, f = 0, 0
    for u in users:
        try:
            await context.bot.send_message(u["id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await update.message.reply_text(f"✅ Duyuru bitti.\nBaşarılı: {s}\nBaşarısız: {f}")

# =========================
# 🏁 ÇALIŞTIRMA
# =========================
async def run_bot():
    if not TOKEN:
        logger.error("❌ TOKEN Çevresel Değişkeni bulunamadı!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Başlangıçta veriyi çek
    await sync_data()

    # Handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yardim", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("hadis", hadis_ver))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    logger.info("🚀 Bot v160 Eksiksiz Olarak Başlatıldı!")
    
    await app.updater.initialize()
    await app.updater.start_polling()
    await app.initialize()
    await app.start()
    
    while True: await asyncio.sleep(1000)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot durduruldu.")
