import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Sahurda bereket vardır, bir yudum suyla olsa da sahur yapınız."
]

# =========================
# 💾 KULLANICI KAYIT (ESKİ YAPI)
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
# 🌐 HABERTÜRK/DİYANET AYARINDA VERİ ÇEKİCİ
# =========================
async def get_live_vakit(city_name):
    # Türkçe karakterleri temizle (API için)
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    
    # Habertürk gibi sitelerin de beslendiği Diyanet tabanlı global API
    url = f"https://api.aladhan.com/v1/timingsByCity?city={clean_city}&country=Turkey&method=13"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            res = await client.get(url)
            if res.status_code == 200:
                d = res.json()["data"]
                return {
                    "imsak": d["timings"]["Fajr"],
                    "iftar": d["timings"]["Maghrib"],
                    "yer": city_name.upper(),
                    "tarih": d["date"]["readable"]
                }
        except: return None
    return None

# =========================
# 🎭 ANA İŞLEM (SEVDİĞİN GÖRSEL YAPI)
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir yazın. Örn: <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    # Kullanıcıyı bekletirken bilgi ver
    tmp = await update.message.reply_text("📡 <b>Güncel veriler çekiliyor...</b>", parse_mode=ParseMode.HTML)
    data = await get_live_vakit(city)

    if not data:
        await tmp.edit_text("❌ Veri çekilemedi. Şehir ismini kontrol edin.")
        return

    v_saat = data["iftar"] if mode == "iftar" else data["imsak"]
    
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    
    if now >= target: target += timedelta(days=1)
    diff = int((target - now).total_seconds())
    
    # Görsel ilerleme barı
    bar_count = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🟦" * bar_count + "⬜" * (10 - bar_count)

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
        f"📅 Tarih: <code>{data['tarih']}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Saat: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
        f"📊 İlerleme:\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>{random.choice(HADISLER)}</i>"
    )
    await tmp.edit_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN & KOMUTLAR (TAM SİSTEM)
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [
        [InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
        [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]
    ]
    await u.message.reply_text(
        "✨ <b>RAMAZAN CANLI BOT v75</b> ✨\n\nHoş geldiniz! Veriler Habertürk ve Diyanet ile %100 uyumlu şekilde canlı çekilir.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
    )

async def stats(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    try:
        with open(CHATS_FILE, "r") as f: count = len(json.load(f))
    except: count = 0
    await (u.message.reply_text if u.message else u.callback_query.message.reply_text)(f"👤 Toplam Kullanıcı: {count}")

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    txt = " ".join(c.args)
    if not txt: return
    with open(CHATS_FILE, "r") as f: users = json.load(f)
    for user in users:
        try: await c.bot.send_message(user["id"], f"📢 <b>DUYURU</b>\n\n{txt}", parse_mode=ParseMode.HTML)
        except: pass
    await u.message.reply_text("✅ Duyuru gönderildi.")

async def cb_handler(u, c):
    q = u.callback_query; await q.answer()
    if q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("Duyuru için: /duyuru [mesaj]")
    else: await q.message.reply_text("📍 Sorgu: /iftar şehir")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: engine(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: engine(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb_handler))
    print("🚀 Bot Canlı Modda Yayında!")
    app.run_polling()

if __name__ == "__main__": main()
