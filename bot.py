import os, json, httpx, pytz, random, logging, asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ⚙️ AYARLAR
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN")
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# LİNKİ BURADAN GÜNCELLEDİM ✅
JSON_URL = "https://raw.githubusercontent.com/Rq7mg/-ftarvakti/main/vakitler.json"

RAMAZAN_START = datetime(2026, 2, 18, tzinfo=pytz.timezone("Europe/Istanbul"))

LOCAL_CACHE = {}
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Oruçlu için iki sevinç vardır: İftar ve Rabbine kavuştuğu an. ✨"
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
async def sync_data():
    global LOCAL_CACHE
    headers = {"User-Agent": "Mozilla/5.0"}
    cache_buster = f"?t={int(datetime.now().timestamp())}"
    
    async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
        try:
            res = await client.get(JSON_URL + cache_buster)
            if res.status_code == 200:
                content = res.json()
                if isinstance(content, dict):
                    LOCAL_CACHE = content
                    logging.info(f"✅ Başarılı! Şehir Sayısı: {len(LOCAL_CACHE)}")
                    return True, "Başarılı"
                else:
                    return False, "JSON formatı hatalı (Sözlük değil)"
            else:
                return False, f"HTTP Hatası: {res.status_code}"
        except Exception as e:
            logging.error(f"❌ Hata: {e}")
            return False, str(e)

# =========================
# 🎭 ANA MOTOR
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    global LOCAL_CACHE
    
    # Eğer cache boşsa, çekmeyi dene
    if not LOCAL_CACHE:
        success, reason = await sync_data()
        if not success:
            await update.message.reply_text(f"❌ <b>Veri Çekme Hatası!</b>\nSebep: <code>{reason}</code>\nLink: {JSON_URL}", parse_mode=ParseMode.HTML)
            return

    city_input = " ".join(context.args).strip() if context.args else None
    if not city_input:
        await update.message.reply_text(f"📍 Örnek: <code>/{mode} istanbul</code>", parse_mode=ParseMode.HTML)
        return

    def format_city_name(name):
        name = name.lower().replace("ı", "i").replace("İ", "i")
        tr_map = str.maketrans("çğöşü", "cgosu")
        return name.translate(tr_map).replace(" ", "")

    city_key = format_city_name(city_input)

    if city_key not in LOCAL_CACHE:
        await update.message.reply_text(
            f"❌ <b>Şehir Bulunamadı!</b>\nSistemde <b>{len(LOCAL_CACHE)}</b> şehir yüklü.\nGirilen: <code>{city_input}</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # Vakit Hesaplama
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    r_day = (now.date() - RAMAZAN_START.date()).days + 1
    
    if r_day < 1 or r_day > 30:
        await update.message.reply_text("🌙 2026 Ramazan ayında değiliz.")
        return

    try:
        v_saat = LOCAL_CACHE[city_key][mode][r_day-1]
        msg = f"🌙 <b>{mode.upper()} | {city_input.upper()}</b>\n⏰ Saat: <code>{v_saat}</code>\n📅 Gün: {r_day}"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("❌ Vakit verisi eksik.")

# =========================
# 🛠 KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌙 Ramazan Botu Hazır!\n/iftar [şehir]\n/sahur [şehir]")

async def yenile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    success, reason = await sync_data()
    msg = "✅ Veriler güncellendi!" if success else f"❌ Hata: {reason}"
    await update.message.reply_text(msg)

# =========================
# 🏁 FİNAL
# =========================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    await sync_data()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yenile", yenile))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"imsak"))) # İmsak listesini kullanır
    
    await app.updater.initialize()
    await app.updater.start_polling()
    await app.initialize()
    await app.start()
    while True: await asyncio.sleep(1000)

if __name__ == "__main__":
    asyncio.run(main())
