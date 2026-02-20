import os, json, httpx, pytz, random, logging, asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# ⚙️ AYARLAR VE LOGLAMA
# =========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
TOKEN = os.environ.get("TOKEN")
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# Zaman Dilimi
TR_TZ = pytz.timezone("Europe/Istanbul")
# 2026 Ramazan Başlangıcı (Diyanet takvimine göre 19 Şubat 2026 Perşembe ilk oruç)
RAMAZAN_START = datetime(2026, 2, 19, tzinfo=TR_TZ)

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Oruçlu için iki sevinç vardır: İftar ve Rabbine kavuştuğu an. ✨",
    "Kim bir oruçluya iftar ettirirse, oruçlunun sevabından bir şey eksilmeden aynı sevap ona da yazılır. ✨"
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def save_user(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    try:
        with open(CHATS_FILE, "r+") as f:
            data = json.load(f)
            if chat_id not in [u.get("id") for u in data]:
                data.append({"id": chat_id, "join_date": datetime.now(TR_TZ).strftime("%Y-%m-%d")})
                f.seek(0); json.dump(data, f); f.truncate()
    except: pass

async def get_vakit_from_api(city):
    """Abdus.dev API'sinden canlı veri çeker"""
    # API varsayılan olarak Türkiye odaklıdır, şehir ismini düzeltip gönderiyoruz
    url = f"https://prayertimes.api.abdus.dev/api/times/today?city={city.lower()}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                return res.json()
            return None
        except:
            return None

# =========================
# 📊 GÖRSEL ARAÇLAR
# =========================
def create_progress_bar(percent):
    percent = max(0, min(100, percent)) # 0-100 arası tut
    done = int(percent / 10)
    bar = "▬" * done + "🔘" + "▬" * max(0, (10 - done - 1))
    return f"<code>{bar}</code> {int(percent)}%"

# =========================
# 🎭 ANA MOTOR (İFTAR/SAHUR)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    save_user(update.effective_chat.id)
    
    city_input = " ".join(context.args).strip() if context.args else None
    if not city_input:
        await update.message.reply_text(f"📍 <b>Kullanım:</b> <code>/{mode} [şehir]</code>\nÖrnek: <code>/{mode} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    # API'den Veri Çek
    data = await get_vakit_from_api(city_input)
    if not data:
        await update.message.reply_text(f"❌ <b>'{city_input}'</b> için vakit bilgisi alınamadı!\nLütfen şehir ismini doğru yazdığınızdan emin olun.", parse_mode=ParseMode.HTML)
        return

    now = datetime.now(TR_TZ)
    # Ramazan günü hesaplama
    r_day = (now.date() - RAMAZAN_START.date()).days + 1
    
    # API'den gelen vakitler (Imsak ve Maghrib)
    v_saat = data['times']['Imsak'] if mode == "sahur" else data['times']['Maghrib']
    
    try:
        target_time = datetime.strptime(v_saat, "%H:%M").time()
        target = datetime.combine(now.date(), target_time).replace(tzinfo=TR_TZ)
        
        if now > target: target += timedelta(days=1)
        
        diff = target - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        header = "🌅 SAHUR VAKTİ" if mode == "sahur" else "🌇 İFTAR VAKTİ"
        icon = "🌙" if mode == "sahur" else "🕌"
        
        # Ramazan dışındaysa gün bilgisini gösterme veya farklı mesaj ver
        gun_str = f"📅 <b>Ramazan'ın {r_day}. Günü</b>\n" if 1 <= r_day <= 30 else "🗓 <b>Bugünün Vakitleri</b>\n"
        progress_str = f"📊 <b>Günün İlerlemesi:</b>\n{create_progress_bar((r_day/30)*100)}\n" if 1 <= r_day <= 30 else ""

        msg = (
            f"{icon} <b>{header} | {city_input.upper()}</b>\n"
            f"{gun_str}"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Vakit: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <b>{hours} saat {minutes} dakika</b>\n\n"
            f"{progress_str}"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📢 <i>{random.choice(HADISLER)}</i>\n"
            f"🕒 <i>Sistem Saati: {now.strftime('%H:%M')}</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Hesaplama Hatası:</b> {e}", parse_mode=ParseMode.HTML)

# =========================
# 🛠 KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    welcome = (
        "✨ <b>Hoş Geldiniz! Ben Ramazan Asistanı</b> ✨\n\n"
        "Size en doğru vakitleri API üzerinden canlı sunuyorum.\n\n"
        "📍 <b>Hızlı Komutlar:</b>\n"
        "👉 /iftar <code>[şehir]</code>\n"
        "👉 /sahur <code>[şehir]</code>\n"
        "👉 /hadis - Günün Hadisi\n"
        "👉 /durum - Sistem Durumu\n\n"
        "<i>Huzurlu bir Ramazan dilerim...</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)

async def hadis_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <b>Günün Hadis-i Şerifi:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TR_TZ).strftime("%H:%M:%S")
    msg = (
        f"🖥 <b>Sistem Durumu</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📡 API Bağlantısı: 🟢 Aktif (Canlı)\n"
        f"🌍 Kaynak: <code>abdus.dev</code>\n"
        f"🕒 Bölge Saati: <code>{now}</code>\n"
        f"🗓 Hedef Yıl: <code>2026</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def admin_duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text: return
    
    if not os.path.exists(CHATS_FILE): return
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    s, f = 0, 0
    for u in users:
        try:
            await context.bot.send_message(u["id"], f"📢 <b>RAMAZAN DUYURUSU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await update.message.reply_text(f"✅ Duyuru Gönderildi!\nBaşarılı: {s} | Başarısız: {f}")

# =========================
# 🏁 ÇALIŞTIRMA
# =========================
async def run_main():
    if not TOKEN:
        print("❌ HATA: TOKEN bulunamadı!")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("hadis", hadis_ver))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("duyuru", admin_duyuru))
    
    print("🚀 Ramazan Asistanı v2.5 (API Mode) Başlatıldı!")
    
    await app.updater.initialize()
    await app.updater.start_polling()
    await app.initialize()
    await app.start()
    while True: await asyncio.sleep(1000)

if __name__ == "__main__":
    try:
        asyncio.run(run_main())
    except (KeyboardInterrupt, SystemExit):
        pass
