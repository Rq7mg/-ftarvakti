import os, json, httpx, pytz, random, logging, asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE STATS
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# 2026 Ramazan Başlangıcı (18 Şubat 2026)
RAMAZAN_START = datetime(2026, 2, 18, tzinfo=pytz.timezone("Europe/Istanbul"))

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. ✨",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır. ✨",
    "Ramazan ayı girdiği zaman cennet kapıları açılır. ✨",
    "Sahur yapınız, zira sahurda bolluk ve bereket vardır. ✨",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an. ✨"
]

# =========================
# 💾 KULLANICI KAYDI (STATS İÇİN)
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
# 🌐 ENGEL TANIMAZ YERLİ API MOTORU
# =========================
async def get_vakit(city_name):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    
    # Engellenmeyen yerli yansı API
    url = f"https://ezanvakti.herokuapp.com/vakitler?sehir={clean_city}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                d = res.json()[0]
                return {"imsak": d["Imsak"], "iftar": d["Aksam"], "yer": city_name.upper()}
        except: return None
    return None

# =========================
# 🎭 ANA İŞLEM (GÖRSEL ŞÖLEN)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 <b>Kullanım:</b> <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    status = await update.message.reply_text("💎 <b>Veriler Hazırlanıyor...</b>", parse_mode=ParseMode.HTML)
    data = await get_vakit(city)

    if not data:
        await status.edit_text("❌ Sunucu hatası! Lütfen şehir ismini kontrol edip tekrar deneyin.")
        return

    v_saat = data["iftar"] if mode == "iftar" else data["imsak"]
    
    # Zaman ve Ramazan Günü Hesabı
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    r_day = (now - RAMAZAN_START).days + 1
    
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    if now >= target: target += timedelta(days=1)
    diff = int((target - now).total_seconds())
    
    # Dinamik İlerleme Çubuğu (Bar)
    p = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🔘" * p + "⚪" * (10 - p)

    msg = (
        f"🌟 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
        f"📅 <b>Ramazan'ın {max(1, r_day)}. Günü</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Saat: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <b>{diff//3600} saat {(diff%3600)//60} dakika</b>\n\n"
        f"📊 <b>Vakte Kalan Süre:</b>\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"📢 <i>{random.choice(HADISLER)}</i>"
    )
    
    kb = [[InlineKeyboardButton("🔄 Yenile", callback_data=f'r_{mode}_{city}')]]
    await status.edit_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN & KOMUTLAR
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [
        [InlineKeyboardButton("🍽 İftar", callback_data='btn_i'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_s')],
        [InlineKeyboardButton("📊 İstatistik", callback_data='stats'), InlineKeyboardButton("📢 Duyuru", callback_data='duyuru')]
    ]
    await u.message.reply_text(
        "✨ <b>RAMAZAN PRESTIGE v130</b> ✨\n\nHoş geldiniz! En güncel Diyanet verileriyle, Ramazan ayını saniyesi saniyesine takip edin.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
    )

async def handle_callback(u, c):
    q = u.callback_query; data = q.data; await q.answer()
    if data.startswith('r_'): # Yenileme butonu
        _, mode, city = data.split('_')
        # Engine fonksiyonunu args ile simüle et
        class Obj: pass
        update_mock = Obj(); update_mock.message = q.message; update_mock.effective_user = q.from_user
        context_mock = Obj(); context_mock.args = [city]; context_mock.bot = c.bot
        await engine(q, context_mock, mode)
    elif data == 'stats':
        if q.from_user.id in ADMIN_IDS:
            with open(CHATS_FILE, "r") as f: count = len(json.load(f))
            await q.message.reply_text(f"👤 <b>Toplam Kullanıcı:</b> {count}", parse_mode=ParseMode.HTML)
    elif data == 'btn_i': await q.message.reply_text("📍 İftar için: <code>/iftar Şehir</code>", parse_mode=ParseMode.HTML)
    elif data == 'btn_s': await q.message.reply_text("📍 Sahur için: <code>/sahur Şehir</code>", parse_mode=ParseMode.HTML)

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    text = " ".join(c.args)
    if not text:
        await u.message.reply_text("❌ Kullanım: /duyuru [mesaj]")
        return
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    for user in users:
        try: await c.bot.send_message(user["id"], f"🔔 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
        except: pass
    await u.message.reply_text("✅ Duyuru başarıyla iletildi.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🚀 Bot v130 Prestige Yayında!")
    app.run_polling()

if __name__ == "__main__": main()
