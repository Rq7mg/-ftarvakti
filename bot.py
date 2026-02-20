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
IMSAKIYE_CACHE = {} 

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def save_chat(chat_id):
    chats = load_chats()
    if not any(c.get("chat_id") == chat_id for c in chats):
        chats.append({"chat_id": chat_id})
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(chats, f)

# =========================
# 📡 İMSAKİYE MOTORU
# =========================
async def get_imsakiye(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    if city_clean in IMSAKIYE_CACHE: return IMSAKIYE_CACHE[city_clean]
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            url = f"https://api.aladhan.com/v1/calendarByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url)
            if res.status_code == 200:
                data = res.json()["data"]
                IMSAKIYE_CACHE[city_clean] = data
                return data
        except: return None
    return None

# =========================
# 🎭 VAKİT İŞLEYİCİLER (LAMBDA HATASI GİDERİLDİ)
# =========================
async def iftar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_motoru(update, context, "Maghrib", "İFTAR")

async def sahur_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_motoru(update, context, "Fajr", "SAHUR")

async def vakit_motoru(update: Update, context: ContextTypes.DEFAULT_TYPE, key, label):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Şehir yazın. Örn: <code>/{label.lower()} istanbul</code>", parse_mode=ParseMode.HTML)
        return
    
    status = await update.message.reply_text("⏳ Sorgulanıyor...")
    data = await get_imsakiye(city)
    
    if not data:
        await status.edit_text("❌ Veri alınamadı. Şehir ismini kontrol edin.")
        return

    try:
        tz = pytz.timezone("Europe/Istanbul")
        now = datetime.now(tz)
        day_data = data[now.day - 1]["timings"]
        v_saat = day_data[key].split(" ")[0]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
        if now >= target:
            day_data = data[now.day]["timings"]
            v_saat = day_data[key].split(" ")[0]
            target = (target + timedelta(days=1)).replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]))

        diff = int((target - now).total_seconds())
        bar = "🟦" * int(10 * (1 - diff/57600)) + "⬜" * (10 - int(10 * (1 - diff/57600)))
        
        msg = (f"🌙 <b>{label} VAKTİ | {city.upper()}</b>\n"
               f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
               f"⏰ Vakit: <code>{v_saat}</code>\n"
               f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
               f"{bar}\n"
               f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
               f"✨ <i>{random.choice(HADISLER)}</i>")
        await status.edit_text(msg, parse_mode=ParseMode.HTML)
    except: await status.edit_text("⚠️ Bir hata oluştu.")

# =========================
# 🛠️ ADMIN & DİĞER
# =========================
async def stats(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    await u.message.reply_text(f"📊 Toplam Kullanıcı: {len(load_chats())}")

async def duyuru(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    text = " ".join(c.args)
    if not text: return
    for user in load_chats():
        try: await c.bot.send_message(user["chat_id"], f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
        except: pass
    await u.message.reply_text("✅ Gönderildi.")

async def start(u, c):
    save_chat(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📜 Hadis", callback_data='h')]]
    await u.message.reply_text("✨ <b>RAMAZAN BOT v38</b> ✨\nŞehir yazarak vakitleri öğrenebilirsiniz.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def cb(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 {random.choice(HADISLER)}")
    else: await q.message.reply_text("📍 Sorgu için: <code>/iftar şehir</code> yazın.", parse_mode=ParseMode.HTML)

# =========================
# 🏁 ANA ÇALIŞTIRICI
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd)) # Lambda kaldırıldı, hata çözüldü!
    app.add_handler(CommandHandler("sahur", sahur_cmd)) # Lambda kaldırıldı, hata çözüldü!
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(cb))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat(u.effective_chat.id)))
    print("🚀 Bot v38 Loglardaki hatayı çözerek başladı!")
    app.run_polling()

if __name__ == "__main__": main()
