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
JSON_URL = "https://raw.githubusercontent.com/Rq7mg/-ftarvakti/main/vakitler.json"

# Zaman Dilimi ve Başlangıç
TR_TZ = pytz.timezone("Europe/Istanbul")
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=TR_TZ)

# Global Hafıza
LOCAL_CACHE = {}
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

async def sync_data():
    global LOCAL_CACHE
    headers = {"User-Agent": "RamazanAsistaniBot/2.0"}
    cache_buster = f"?t={int(datetime.now().timestamp())}"
    async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
        try:
            res = await client.get(JSON_URL + cache_buster)
            if res.status_code == 200:
                LOCAL_CACHE = res.json()
                logging.info(f"✅ Veriler senkronize edildi. Şehir sayısı: {len(LOCAL_CACHE)}")
                return True, len(LOCAL_CACHE)
            return False, f"Hata Kodu: {res.status_code}"
        except Exception as e:
            return False, str(e)

# =========================
# 📊 GÖRSEL ARAÇLAR
# =========================
def create_progress_bar(percent):
    percent = max(0, min(100, percent))
    done = int(percent / 10)
    bar = "▬" * done + "🔘" + "▬" * (10 - done - 1 if 10 - done - 1 > 0 else 0)
    
    if percent == 100:
        bar = "▬" * 10
    
    return f"<code>{bar}</code> {int(percent)}%"

# =========================
# 🎭 ANA MOTOR (İFTAR/SAHUR)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    save_user(update.effective_chat.id)
    
    if not LOCAL_CACHE:
        success, info = await sync_data()
        if not success:
            await update.message.reply_text(f"❌ <b>Veri Bağlantı Hatası!</b>\n<code>{info}</code>", parse_mode=ParseMode.HTML)
            return

    city_input = " ".join(context.args).strip() if context.args else None
    if not city_input:
        await update.message.reply_text(f"📍 <b>Kullanım:</b> <code>/{mode} [şehir]</code>\nÖrnek: <code>/{mode} Ankara</code>", parse_mode=ParseMode.HTML)
        return

    def format_city(name):
        name = name.lower().replace("ı", "i").replace("İ", "i")
        tr_map = str.maketrans("çğöşü", "cgosu")
        return name.translate(tr_map).replace(" ", "")

    city_key = format_city(city_input)

    if city_key not in LOCAL_CACHE:
        await update.message.reply_text(f"❌ <b>'{city_input}'</b> şehri bulunamadı!\nŞu an {len(LOCAL_CACHE)} şehir yüklü.", parse_mode=ParseMode.HTML)
        return

    now = datetime.now(TR_TZ)
    r_day = (now.date() - RAMAZAN_START.date()).days + 1
    
    if r_day < 1 or r_day > 30:
        await update.message.reply_text("🌙 <b>Ramazan Ayı Bekleniyor...</b>\n2026 Ramazan henüz başlamadı.", parse_mode=ParseMode.HTML)
        return

    try:
        imsak_vakti_str = LOCAL_CACHE[city_key]["imsak"][r_day-1]
        iftar_vakti_str = LOCAL_CACHE[city_key]["iftar"][r_day-1]
        
        imsak_dt = now.replace(hour=int(imsak_vakti_str.split(":")[0]), minute=int(imsak_vakti_str.split(":")[1]), second=0, microsecond=0)
        iftar_dt = now.replace(hour=int(iftar_vakti_str.split(":")[0]), minute=int(iftar_vakti_str.split(":")[1]), second=0, microsecond=0)

        json_key = "imsak" if mode == "sahur" else "iftar"
        v_saat = LOCAL_CACHE[city_key][json_key][r_day-1]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        
        if now > target: 
            target += timedelta(days=1)
        
        diff = target - now
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)

        # İlerleme Çubuğu Hesabı
        progress_percent = 0
        if mode == "iftar":
            if now > imsak_dt and now < iftar_dt:
                toplam_sure = (iftar_dt - imsak_dt).total_seconds()
                gecen_sure = (now - imsak_dt).total_seconds()
                progress_percent = (gecen_sure / toplam_sure) * 100
            elif now >= iftar_dt:
                progress_percent = 100
            elif now <= imsak_dt:
                progress_percent = 0
        else:
             if r_day > 1:
                  onceki_iftar_str = LOCAL_CACHE[city_key]["iftar"][r_day-2]
                  onceki_iftar_dt = (now - timedelta(days=1)).replace(hour=int(onceki_iftar_str.split(":")[0]), minute=int(onceki_iftar_str.split(":")[1]), second=0, microsecond=0)
             else:
                  onceki_iftar_dt = (now - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
             
             if now > imsak_dt:
                  sonraki_imsak_str = LOCAL_CACHE[city_key]["imsak"][r_day] if r_day < 30 else "05:00"
                  hedef_imsak_dt = (now + timedelta(days=1)).replace(hour=int(sonraki_imsak_str.split(":")[0]), minute=int(sonraki_imsak_str.split(":")[1]), second=0, microsecond=0)
                  toplam_sure = (hedef_imsak_dt - iftar_dt).total_seconds()
                  gecen_sure = (now - iftar_dt).total_seconds()
             else:
                  toplam_sure = (imsak_dt - onceki_iftar_dt).total_seconds()
                  gecen_sure = (now - onceki_iftar_dt).total_seconds()
                  
             if toplam_sure > 0 and gecen_sure > 0:
                 progress_percent = (gecen_sure / toplam_sure) * 100
             else:
                 progress_percent = 0

        header = "🌅 SAHUR VAKTİ" if mode == "sahur" else "🌇 İFTAR VAKTİ"
        icon = "🌙" if mode == "sahur" else "🕌"
        
        msg = (
            f"{icon} <b>{header} | {city_input.upper()}</b>\n"
            f"📅 <b>Ramazan'ın {r_day}. Günü</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Vakit: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <b>{hours} saat {minutes} dakika</b>\n\n"
            f"📊 <b>Günün İlerlemesi:</b>\n{create_progress_bar(progress_percent)}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📢 <i>{random.choice(HADISLER)}</i>\n"
            f"🕒 <i>Sistem Saati: {now.strftime('%H:%M')}</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ <b>Veri Hatası:</b> {e}", parse_mode=ParseMode.HTML)

# =========================
# 🛠 KOMUTLAR VE FONKSİYONLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    welcome = (
        "✨ <b>Hoş Geldiniz! Ben Ramazan Asistanı</b> ✨\n\n"
        "Size en doğru vakitleri ve manevi paylaşımları sunmak için buradayım.\n\n"
        "📍 <b>Hızlı Komutlar:</b>\n"
        "👉 /iftar <code>[şehir]</code>\n"
        "👉 /sahur <code>[şehir]</code>\n"
        "👉 /hadis - Günün Hadisi\n"
        "👉 /durum - Sistem Durumu\n"
        "👉 /stats - Bot İstatistikleri\n\n"
        "<i>Huzurlu bir Ramazan dilerim...</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)

async def hadis_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <b>Günün Hadis-i Şerifi:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 Aktif" if LOCAL_CACHE else "🔴 Veri Yok"
    now = datetime.now(TR_TZ).strftime("%H:%M:%S")
    msg = (
        f"🖥 <b>Sistem Durumu</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📡 Veri Bağlantısı: {status}\n"
        f"📍 Yüklü Şehir: <code>{len(LOCAL_CACHE)}</code>\n"
        f"🕒 Bölge Saati: <code>{now}</code>\n"
        f"🗓 Hedef Yıl: <code>2026</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update.effective_chat.id)
    try:
        if os.path.exists(CHATS_FILE):
            with open(CHATS_FILE, "r") as f:
                users = json.load(f)
                user_count = len(users)
        else:
            user_count = 0
    except:
        user_count = 0

    msg = (
        f"📊 <b>Bot İstatistikleri</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"👥 Toplam Kullanıcı: <code>{user_count}</code>\n"
        f"📍 Yüklü Şehir (JSON): <code>{len(LOCAL_CACHE)}</code>\n"
        f"🛡️ Sunucu Durumu: <code>Aktif</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def admin_duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text: return
    
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    s, f = 0, 0
    for u in users:
        try:
            await context.bot.send_message(u["id"], f"📢 <b>RAMAZAN DUYURUSU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await update.message.reply_text(f"✅ Duyuru Gönderildi!\nBaşarılı: {s} | Başarısız: {f}")

async def admin_yenile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    success, info = await sync_data()
    msg = f"✅ <b>Yenilendi!</b> {info} şehir yüklü." if success else f"❌ <b>Başarısız!</b> {info}"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🏁 ÇALIŞTIRMA
# =========================
async def run_main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    await sync_data()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("hadis", hadis_ver))
    app.add_handler(CommandHandler("durum", durum))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("yenile", admin_yenile))
    app.add_handler(CommandHandler("duyuru", admin_duyuru))
    
    print("🚀 Ramazan Asistanı Başlatıldı!")
    
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
