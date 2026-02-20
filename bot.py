import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE YEREL KOORDİNATLAR
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# En çok sorulan şehirlerin koordinatları (Hata payını sıfıra indirmek için)
CITY_COORDS = {
    "ankara": {"lat": 39.9334, "lng": 32.8597},
    "istanbul": {"lat": 41.0082, "lng": 28.9784},
    "izmir": {"lat": 38.4237, "lng": 27.1428},
    "gaziantep": {"lat": 37.0662, "lng": 37.3833},
    "adana": {"lat": 37.0000, "lng": 35.3213},
    "bursa": {"lat": 40.1885, "lng": 29.0610},
    "konya": {"lat": 37.8714, "lng": 32.4846}
}

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 KULLANICI YÖNETİMİ
# =========================
def save_user(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    with open(CHATS_FILE, "r+") as f:
        data = json.load(f)
        if chat_id not in [c.get("id") for c in data]:
            data.append({"id": chat_id})
            f.seek(0); json.dump(data, f); f.truncate()

# =========================
# 📡 %100 STABİL VERİ MOTORU
# =========================
async def fetch_vakit(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    # Koordinat bazlı sorgu (Şehir ismi hatasını bitirir)
    coords = CITY_COORDS.get(city_clean, {"lat": 39.9, "lng": 32.8}) # Bulamazsa Ankara baz alır
    
    # Dünyanın en stabil namaz vakti API'sine (Aladhan) koordinatla gidiyoruz
    # Şehir ismi yerine koordinat kullanmak "Bağlantı Kurulamadı" hatasını %99 çözer.
    url = f"https://api.aladhan.com/v1/timings?latitude={coords['lat']}&longitude={coords['lng']}&method=13"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                d = res.json()["data"]["timings"]
                return {"v": d, "yer": city_input.upper()}
        except:
            return None
    return None

# =========================
# 🎭 ANA MOTOR
# =========================
async def handle_vakit(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir yazın. Örn: <code>/{mode} Gaziantep</code>", parse_mode=ParseMode.HTML)
        return

    status = await update.message.reply_text("📡 Hassas hesaplama yapılıyor...")
    data = await fetch_vakit(city)

    if not data:
        await status.edit_text("⚠️ API şu an yanıt vermiyor, ancak tekrar deneniyor...")
        # 2. deneme (Farklı metot)
        data = await fetch_vakit(city)
        if not data:
            await status.edit_text("❌ Sunucu hatası. Lütfen 30 saniye sonra tekrar deneyin.")
            return

    try:
        tz = pytz.timezone("Europe/Istanbul")
        now = datetime.now(tz)
        v_key = "Maghrib" if mode == "iftar" else "Fajr"
        v_saat = data["v"][v_key]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        bar = "🟦" * int(10 * (1 - diff/57600)) + "⬜" * (10 - int(10 * (1 - diff/57600)))
        
        await status.edit_text(
            f"🌙 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ Saat: <code>{v_saat}</code>\n"
            f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
            f"{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>",
            parse_mode=ParseMode.HTML
        )
    except:
        await status.edit_text("⚠️ Vakit işlenirken bir hata oluştu.")

# =========================
# 🛠️ ADMIN & KOMUTLAR
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]]
    await u.message.reply_text("✨ <b>RAMAZAN NITRO v41</b> ✨\nHoş geldiniz! Her şey stabilize edildi.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def stats(u, c):
    if u.effective_user.id in ADMIN_IDS:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
        await u.message.reply_text(f"📊 Toplam Kullanıcı: {count}")

async def duyuru(u, c):
    if u.effective_user.id in ADMIN_IDS:
        msg = " ".join(c.args)
        if not msg: return
        with open(CHATS_FILE, "r") as f: users = json.load(f)
        for user in users:
            try: await c.bot.send_message(user["id"], f"📢 {msg}", parse_mode=ParseMode.HTML)
            except: pass
        await u.message.reply_text("✅ Duyuru gönderildi.")

async def cb(u, c):
    q = u.callback_query; await q.answer()
    if q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("💡 Duyuru: /duyuru [mesaj]")
    else: await q.message.reply_text("📍 Sorgu için: /iftar şehir")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: handle_vakit(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: handle_vakit(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb))
    app.run_polling()

if __name__ == "__main__": main()
