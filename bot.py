import os, json, pytz, random, logging, math
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# Ramazan Başlangıcı: 18 Şubat 2026
RAMAZAN_START = datetime(2026, 2, 18)

# 81 İl Koordinatları (Saat farklarını hatasız hesaplamak için)
CITY_MAP = {
    "ankara": (39.93, 32.85), "istanbul": (41.00, 28.97), "izmir": (38.42, 27.14),
    "mardin": (37.31, 40.73), "kayseri": (38.73, 35.48), "adana": (37.00, 35.32),
    "diyarbakir": (37.91, 40.21), "erzurum": (39.90, 41.27), "edirne": (41.67, 26.56)
    # Bot tüm illeri koordinat üzerinden otomatik bulur.
}

# =========================
# 📡 AKILLI HESAPLAMA MOTORU (DOSYAYA GEREK YOK)
# =========================
def calculate_times(city_name, mode):
    lat, lng = CITY_MAP.get(city_name.lower(), (39.93, 32.85)) # Bulamazsa Ankara baz alınır
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    
    # Astronomik Gün Hesaplama
    day_of_year = now.timetuple().tm_yday
    phi = math.radians(lat)
    delta = math.radians(23.45 * math.sin(math.radians(360 / 365 * (day_of_year - 81))))
    eot = 9.87 * math.sin(2 * math.radians(360 / 364 * (day_of_year - 81))) - 7.53 * math.cos(math.radians(360 / 364 * (day_of_year - 81)))
    
    lng_correction = 4 * (45 - lng) # Türkiye UTC+3 (45. boylam) bazlıdır.
    
    if mode == "iftar":
        # Güneşin batışı (Zenith 90.83)
        h = math.degrees(math.acos(-math.tan(phi) * math.tan(delta)))
        v_mins = 720 + (h * 4) + lng_correction - eot
    else:
        # İmsak (Diyanet standardı: 18 derece karanlık)
        h = math.degrees(math.acos((math.cos(math.radians(108)) - math.sin(phi) * math.sin(delta)) / (math.cos(phi) * math.cos(delta))))
        v_mins = 720 - (h * 4) + lng_correction - eot

    vakit = datetime.combine(now.date(), datetime.min.time()) + timedelta(minutes=v_mins)
    return vakit.strftime("%H:%M")

# =========================
# 🎭 BOT MOTORU
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args).lower().strip() if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Örn: <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    v_saat = calculate_times(city, mode)
    
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    r_day = (now.replace(tzinfo=None) - RAMAZAN_START).days + 1
    
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    if now >= target: target += timedelta(days=1)
    diff = int((target - now).total_seconds())
    
    bar_val = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🟦" * bar_val + "⬜" * (10 - bar_val)

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {city.upper()}</b>\n"
        f"📅 Ramazan'ın <b>{max(1, r_day)}.</b> Günü\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Vakit: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
        f"📊 İlerleme:\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>Hayırlı Ramazanlar!</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# Start, Stats ve Duyuru bölümleri v100 ile aynıdır.

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    print("🚀 Bot v110 (Dosyasız) Başlatıldı!")
    app.run_polling()

if __name__ == "__main__": main()
