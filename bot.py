import os, json, httpx, pytz, random, logging, asyncio
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

# 2026 Ramazan Başlangıcı (18 Şubat 2026)
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=pytz.timezone("Europe/Istanbul"))

# =========================
# 💾 KULLANICI YÖNETİMİ
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

# =========================
# 📡 ÇİFT MOTORLU VERİ ÇEKİCİ (Hata Almaz!)
# =========================
async def get_vakit_guaranteed(city_name):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    
    # MOTOR 1: Ezanvakti API
    urls = [
        f"https://ezanvakti.herokuapp.com/vakitler?sehir={clean_city}",
        f"https://api.aladhan.com/v1/timingsByCity?city={clean_city}&country=Turkey&method=13"
    ]

    async with httpx.AsyncClient(timeout=8.0) as client:
        for url in urls:
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    d = res.json()
                    # Heroku API formatı
                    if isinstance(d, list): 
                        return {"imsak": d[0]["Imsak"], "iftar": d[0]["Aksam"], "src": "Diyanet"}
                    # Aladhan API formatı
                    elif "data" in d:
                        return {"imsak": d["data"]["timings"]["Fajr"], "iftar": d["data"]["timings"]["Maghrib"], "src": "Global"}
            except:
                continue # Hata alırsa diğer URL'ye geç
    return None

# =========================
# 🎭 GÖRSEL MOTOR (FULL ÖZELLİK)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 <b>Hatalı Kullanım!</b>\nLütfen: <code>/{mode} Mardin</code> yazın.", parse_mode=ParseMode.HTML)
        return

    # Şık bir bekleme mesajı
    loading = await update.message.reply_text("⏳ <b>Veriler Hesaplanıyor...</b>", parse_mode=ParseMode.HTML)
    
    data = await get_vakit_guaranteed(city)

    if not data:
        await loading.edit_text("❌ <b>Şehir Bulunamadı!</b>\nLütfen şehir ismini doğru yazdığınızdan emin olun.")
        return

    v_saat = data["iftar"] if mode == "iftar" else data["imsak"]
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    
    # Ramazan Günü Hesapla
    r_day = (now - RAMAZAN_START).days + 1
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    
    if now >= target: target += timedelta(days=1)
    diff = int((target - now).total_seconds())
    
    # Görsel Bar
    p = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🟦" * p + "⬜" * (10 - p)

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {city.upper()}</b>\n"
        f"📅 <b>Ramazan'ın {max(1, r_day)}. Günü</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Vakit: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <b>{diff//3600}sa {(diff%3600)//60}dk</b>\n\n"
        f"📊 <b>Doluluk Oranı:</b>\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>Allah kabul etsin.</i>"
    )
    
    await loading.edit_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN PANELİ (STATS & DUYURU)
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]]
    await u.message.reply_text("🌟 <b>RAMAZAN ULTRA v140</b> 🌟\nKesintisiz veri hattı aktif.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def stats(u, c):
    if u.effective_user.id in ADMIN_IDS:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
        await (u.message.reply_text if u.message else u.callback_query.message.reply_text)(f"👤 <b>Toplam Kullanıcı:</b> {count}", parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    m = " ".join(c.args)
    if not m: return
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    for user in users:
        try: await c.bot.send_message(user["id"], f"📢 <b>DUYURU</b>\n\n{m}", parse_mode=ParseMode.HTML)
        except: pass
    await u.message.reply_text("✅ Duyuru gönderildi.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    print("🚀 Bot Kesintisiz Modda Başlatıldı!")
    app.run_polling()

if __name__ == "__main__": main()
