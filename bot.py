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

# Zaman Dilimi ve Başlangıç
TR_TZ = pytz.timezone("Europe/Istanbul")
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=TR_TZ)

# Global Hafıza
CITY_IDS = {} 
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Oruçlu için iki sevinç vardır: İftar ve Rabbine kavuştuğu an. ✨",
    "Kim bir oruçluya iftar ettirirse, oruçlunun sevabından bir şey eksilmeden aynı sevap ona da yazılır. ✨"
]

# =========================
# 💾 GELİŞMİŞ VERİ YÖNETİMİ
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

def format_city(name):
    if not name: return ""
    name = name.lower().replace("ı", "i").replace("İ", "i")
    tr_map = str.maketrans("çğöşü", "cgosu")
    return name.translate(tr_map).replace(" ", "")

async def sync_data():
    """Diyanet Şehir Listesini Senkronize Eder"""
    global CITY_IDS
    url = "https://ezanvakti.herokuapp.com/sehirler?ulke=2"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()
                CITY_IDS = {format_city(c["SehirAd"]): c["SehirID"] for c in data}
                # Manuel Kontrol (Fallback)
                if "istanbul" not in CITY_IDS: CITY_IDS["istanbul"] = "539"
                if "ankara" not in CITY_IDS: CITY_IDS["ankara"] = "501"
                if "izmir" not in CITY_IDS: CITY_IDS["izmir"] = "535"
                logging.info(f"✅ Şehir listesi yüklendi. Adet: {len(CITY_IDS)}")
                return True, len(CITY_IDS)
            return False, f"Hata: {res.status_code}"
        except Exception as e:
            logging.error(f"Sync Hatası: {e}")
            return False, str(e)

# =========================
# 📊 GÖRSEL ARAÇLAR
# =========================
def create_progress_bar(percent):
    percent = max(0, min(100, percent))
    done = int(percent / 10)
    bar = "▬" * done + "🔘" + "▬" * (10 - done - 1 if done < 10 else 0)
    return f"<code>{bar}</code> {int(percent)}%"

# =========================
# 🎭 ANA MOTOR (İFTAR/SAHUR)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    save_user(update.effective_chat.id)
    
    if not CITY_IDS:
        await sync_data()

    city_input = " ".join(context.args).strip() if context.args else None
    if not city_input:
        await update.message.reply_text(f"📍 <b>Kullanım:</b> <code>/{mode} [şehir]</code>\nÖrnek: <code>/{mode} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    city_key = format_city(city_input)
    if city_key not in CITY_IDS:
        await update.message.reply_text(f"❌ <b>'{city_input}'</b> şehri bulunamadı!\nLütfen geçerli bir il ismi giriniz.", parse_mode=ParseMode.HTML)
        return

    try:
        city_id = CITY_IDS[city_key]
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"https://ezanvakti.herokuapp.com/vakitler?ilce={city_id}")
            vakitler_data = res.json()

        now = datetime.now(TR_TZ)
        bugun_str = now.strftime("%d.%m.%Y")
        vakit_bugun = next((v for v in vakitler_data if v["MiladiTarihKisa"] == bugun_str), None)
        
        if not vakit_bugun:
            await update.message.reply_text("❌ Bugün için vakit bilgisi alınamadı.", parse_mode=ParseMode.HTML)
            return

        v_saat = vakit_bugun["Imsak"] if mode == "sahur" else vakit_bugun["Aksam"]
        target = TR_TZ.localize(datetime.strptime(f"{bugun_str} {v_saat}", "%d.%m.%Y %H:%M"))
        
        # Vakit geçtiyse yarına odaklan
        if now > target:
            yarin = now + timedelta(days=1)
            yarin_str = yarin.strftime("%d.%m.%Y")
            vakit_yarin = next((v for v in vakitler_data if v["MiladiTarihKisa"] == yarin_str), None)
            if vakit_yarin:
                v_saat = vakit_yarin["Imsak"] if mode == "sahur" else vakit_yarin["Aksam"]
                target = TR_TZ.localize(datetime.strptime(f"{yarin_str} {v_saat}", "%d.%m.%Y %H:%M"))

        diff = target - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        r_day = (now.date() - RAMAZAN_START.date()).days + 1
        header = "🌅 SAHUR VAKTİ" if mode == "sahur" else "🌇 İFTAR VAKTİ"
        icon = "🌙" if mode == "sahur" else "🕌"
        
        msg = (
            f"{icon} <b>{header} | {city_input.upper()}</b>\n"
            f"📅 <b>Ramazan'ın {max(1, min(30, r_day))}. Günü</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Vakit: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <b>{hours} saat {minutes} dakika</b>\n\n"
            f"📊 <b>Günün İlerlemesi:</b>\n{create_progress_bar((max(1, min(30, r_day))/30)*100)}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📢 <i>{random.choice(HADISLER)}</i>\n"
            f"🕒 <i>Sistem Saati: {now.strftime('%H:%M')}</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ <b>Veri hatası oluştu.</b> Lütfen daha sonra tekrar deneyin.", parse_mode=ParseMode.HTML)

# =========================
# 🛠 KOMUTLAR VE FONKSİYONLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    welcome = (
        "✨ <b>Hoş Geldiniz! Ben Ramazan Asistanı</b> ✨\n\n"
        "Size en doğru vakitleri Diyanet üzerinden sunuyorum.\n\n"
        "📍 <b>Komutlar:</b>\n"
        "👉 /iftar <code>[şehir]</code>\n"
        "👉 /sahur <code>[şehir]</code>\n"
        "👉 /hadis - Günün Hadisi\n"
        "👉 /durum - Sistem Durumu\n"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)

async def hadis_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <b>Günün Hadis-i Şerifi:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 Aktif" if CITY_IDS else "🔴 Veri Yok"
    now = datetime.now(TR_TZ).strftime("%H:%M:%S")
    msg = (
        f"🖥 <b>Sistem Durumu</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📡 Diyanet API: {status}\n"
        f"🕒 Sistem Saati: <code>{now}</code>\n"
        f"🗓 Hedef Yıl: <code>2026</code>\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def admin_duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text or not os.path.exists(CHATS_FILE): return
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    for u in users:
        try:
            await context.bot.send_message(u["id"], f"📢 <b>RAMAZAN DUYURUSU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text("✅ Duyuru gönderildi.")

async def admin_yenile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    success, info = await sync_data()
    msg = f"✅ Şehirler güncellendi!" if success else f"❌ Hata: {info}"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🏁 ÇALIŞTIRMA
# =========================
async def run_main():
    if not TOKEN:
        print("❌ HATA: TOKEN bulunamadı!")
        return
        
    app = ApplicationBuilder().token(TOKEN).build()
    await sync_data()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("hadis", hadis_ver))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("yenile", admin_yenile))
    app.add_handler(CommandHandler("duyuru", admin_duyuru))
    
    print("🚀 Ramazan Asistanı v2.2 Başlatıldı!")
    
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
