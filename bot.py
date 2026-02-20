import os, json, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE SABİT VERİLER
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# Diyanet verilerine göre Ankara (0) merkezli dakika farkları
# Doğudakiler (-) eksi, Batıdakiler (+) artı dakika alır.
TR_CITY_DATA = {
    "ankara": {"offset": 0}, 
    "istanbul": {"offset": 12},
    "izmir": {"offset": 21}, 
    "gaziantep": {"offset": -18},
    "adana": {"offset": -10}, 
    "bursa": {"offset": 10},
    "konya": {"offset": -2}, 
    "antalya": {"offset": 1},
    "diyarbakir": {"offset": -24}, 
    "samsun": {"offset": -10},
    "erzurum": {"offset": -31},
    "trabzon": {"offset": -22}
}

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 KAYIT SİSTEMİ
# =========================
def save_user(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    with open(CHATS_FILE, "r+") as f:
        try:
            data = json.load(f)
        except: data = []
        if chat_id not in [u.get("id") for u in data]:
            data.append({"id": chat_id})
            f.seek(0); json.dump(data, f); f.truncate()

# =========================
# 📡 DÜZELTİLMİŞ HESAPLAMA MOTORU
# =========================
def calculate_ramadan_times(city_name):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    
    # Şehir listede yoksa Ankara'yı baz al ama hata verme
    city_info = TR_CITY_DATA.get(clean_city, TR_CITY_DATA["ankara"])
    
    # 20 Şubat 2026 Ankara Diyanet Vakitleri (Referans)
    base_imsak = datetime.strptime("06:05", "%H:%M")
    base_aksam = datetime.strptime("18:37", "%H:%M")
    
    # Meridyen düzeltmesi: Ankara'dan farkı ekle/çıkar
    correction = city_info["offset"]
    
    imsak = (base_imsak + timedelta(minutes=correction)).strftime("%H:%M")
    aksam = (base_aksam + timedelta(minutes=correction)).strftime("%H:%M")
    
    return {"imsak": imsak, "aksam": aksam, "yer": city_name.upper()}

# =========================
# 🎭 ANA İŞLEM FONKSİYONLARI
# =========================
async def handle_request(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir girin. Örn: <code>/{mode} Gaziantep</code>", parse_mode=ParseMode.HTML)
        return

    data = calculate_ramadan_times(city)
    v_saat = data["aksam"] if mode == "iftar" else data["imsak"]
    
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    if now >= target: target += timedelta(days=1)
    
    diff = int((target - now).total_seconds())
    bar_count = min(10, max(0, int(10 * (1 - diff/57600))))
    bar = "🟦" * bar_count + "⬜" * (10 - bar_count)

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Saat: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
        f"📊 İlerleme:\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>{random.choice(HADISLER)}</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN PANELİ
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]]
    await u.message.reply_text("✨ <b>RAMAZAN ATOMIK v42.1</b> ✨\nSaatler şehir bazlı güncellendi. Sorgu için şehir yazabilirsin!", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def stats(u, c):
    if u.effective_user.id in ADMIN_IDS:
        try:
            with open(CHATS_FILE, "r") as f: count = len(json.load(f))
        except: count = 0
        await u.message.reply_text(f"📊 Toplam Kullanıcı: {count}")

async def duyuru(u, c):
    if u.effective_user.id in ADMIN_IDS:
        txt = " ".join(c.args)
        if not txt: return
        try:
            with open(CHATS_FILE, "r") as f: users = json.load(f)
        except: return
        for user in users:
            try: await c.bot.send_message(user["id"], f"📢 {txt}", parse_mode=ParseMode.HTML)
            except: pass
        await u.message.reply_text("✅ Duyuru gönderildi.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: handle_request(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: handle_request(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.run_polling()

if __name__ == "__main__": main()
