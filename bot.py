import os, json, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE VERİTABANI
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# 2026 RAMAZAN BAŞLANGICI: 18 Şubat 2026 (Referans olarak alınmıştır)
RAMAZAN_BASLANGIC = datetime(2026, 2, 18)

TR_CITY_DATA = {
    "adana": {"offset": -10}, "adiyaman": {"offset": -17}, "afyonkarahisar": {"offset": 9}, "agri": {"offset": -38},
    "amasya": {"offset": -6}, "ankara": {"offset": 0}, "antalya": {"offset": 1}, "artvin": {"offset": -27},
    "aydin": {"offset": 19}, "balikesir": {"offset": 18}, "bilecik": {"offset": 9}, "bingol": {"offset": -26},
    "bitlis": {"offset": -32}, "bolu": {"offset": 5}, "burdur": {"offset": 3}, "bursa": {"offset": 12},
    "canakkale": {"offset": 23}, "cankiri": {"offset": -2}, "corum": {"offset": -4}, "denizli": {"offset": 13},
    "diyarbakir": {"offset": -24}, "edirne": {"offset": 23}, "elazig": {"offset": -21}, "erzincan": {"offset": -18},
    "erzurum": {"offset": -31}, "eskisehir": {"offset": 6}, "gaziantep": {"offset": -18}, "giresun": {"offset": -14},
    "gumushane": {"offset": -18}, "hakkari": {"offset": -44}, "hatay": {"offset": -14}, "isparta": {"offset": 4},
    "mersin": {"offset": -8}, "istanbul": {"offset": 12}, "izmir": {"offset": 21}, "kars": {"offset": -38},
    "kastamonu": {"offset": -1}, "kayseri": {"offset": -6}, "kirklareli": {"offset": 21}, "kirsehir": {"offset": -3},
    "kocaeli": {"offset": 10}, "konya": {"offset": -2}, "kutahya": {"offset": 9}, "malatya": {"offset": -17},
    "manisa": {"offset": 20}, "kahramanmaras": {"offset": -14}, "mardin": {"offset": -29}, "mugla": {"offset": 15},
    "mus": {"offset": -31}, "nevsehir": {"offset": -5}, "nigde": {"offset": -7}, "ordu": {"offset": -12},
    "rize": {"offset": -22}, "sakarya": {"offset": 9}, "samsun": {"offset": -10}, "siirt": {"offset": -33},
    "sinop": {"offset": -5}, "sivas": {"offset": -11}, "tekirdag": {"offset": 18}, "tokat": {"offset": -8},
    "trabzon": {"offset": -20}, "tunceli": {"offset": -22}, "sanliurfa": {"offset": -21}, "usak": {"offset": 12},
    "van": {"offset": -41}, "yozgat": {"offset": -3}, "zonguldak": {"offset": 6}, "aksaray": {"offset": -4},
    "bayburt": {"offset": -23}, "karaman": {"offset": -4}, "kirikkale": {"offset": -1}, "batman": {"offset": -28},
    "sirnak": {"offset": -36}, "bartin": {"offset": 3}, "ardahan": {"offset": -35}, "igdir": {"offset": -44},
    "yalova": {"offset": 11}, "karabuk": {"offset": 3}, "kilis": {"offset": -18}, "osmaniye": {"offset": -12},
    "duzce": {"offset": 7}
}

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an."
]

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def save_user(chat_id):
    if not os.path.exists(CHATS_FILE):
        with open(CHATS_FILE, "w") as f: json.dump([], f)
    with open(CHATS_FILE, "r+") as f:
        try: data = json.load(f)
        except: data = []
        if chat_id not in [u.get("id") for u in data]:
            data.append({"id": chat_id})
            f.seek(0); json.dump(data, f); f.truncate()

# =========================
# 📡 AKILLI HESAPLAMA MOTORU
# =========================
def calculate_smart_times(city_name):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    clean_city = city_name.translate(tr_map).lower().strip()
    city_info = TR_CITY_DATA.get(clean_city, TR_CITY_DATA["ankara"])
    
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    
    # Ramazan'ın kaçıncı günündeyiz?
    diff_days = (now.replace(tzinfo=None) - RAMAZAN_BASLANGIC).days + 1
    ramazan_gunu = max(1, min(30, diff_days))
    
    # 20 Şubat Ankara Baz Vakitler
    base_imsak = datetime.strptime("06:05", "%H:%M")
    base_aksam = datetime.strptime("18:37", "%H:%M")
    
    # Referans gün (20 Şubat) ile bugün arasındaki farka göre kaydırma
    ref_date = datetime(2026, 2, 20)
    days_from_ref = (now.replace(tzinfo=None) - ref_date).days
    
    # Günlük değişim: İftar +1 dk, İmsak -1.5 dk
    shift_imsak = days_from_ref * -1.5
    shift_aksam = days_from_ref * 1.0
    
    correction = city_info["offset"]
    
    imsak = (base_imsak + timedelta(minutes=correction + shift_imsak)).strftime("%H:%M")
    aksam = (base_aksam + timedelta(minutes=correction + shift_aksam)).strftime("%H:%M")
    
    return {"imsak": imsak, "aksam": aksam, "gun": ramazan_gunu, "yer": city_name.upper()}

# =========================
# 🎭 ANA İŞLEMCİ
# =========================
async def handle_vakit(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text(f"📍 Lütfen şehir girin. Örn: <code>/{mode} Mardin</code>", parse_mode=ParseMode.HTML)
        return

    data = calculate_smart_times(city)
    v_saat = data["aksam"] if mode == "iftar" else data["imsak"]
    
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz)
    target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0)
    if now >= target: target += timedelta(days=1)
    
    diff = int((target - now).total_seconds())
    bar = "🟦" * min(10, max(0, int(10 * (1 - diff/57600)))) + "⬜" * (10 - min(10, max(0, int(10 * (1 - diff/57600)))))

    msg = (
        f"🌙 <b>{mode.upper()} VAKTİ | {data['yer']}</b>\n"
        f"📅 Ramazan'ın <b>{data['gun']}.</b> Günü\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ Saat: <code>{v_saat}</code>\n"
        f"⏳ Kalan: <code>{diff//3600}sa {(diff%3600)//60}dk</code>\n\n"
        f"📊 İlerleme:\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>{random.choice(HADISLER)}</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🛠️ ADMIN & BOT FONKSİYONLARI
# =========================
async def start(u, c):
    save_user(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar", callback_data='i'), InlineKeyboardButton("🥣 Sahur", callback_data='s')],
          [InlineKeyboardButton("📊 Stats", callback_data='st'), InlineKeyboardButton("📢 Duyuru", callback_data='dy')]]
    await u.message.reply_text("✨ <b>RAMAZAN AKILLI BOT v45</b> ✨\nAPI gerektirmez, %100 kararlı çalışır.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

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
        with open(CHATS_FILE, "r") as f: users = json.load(f)
        for user in users:
            try: await c.bot.send_message(user["id"], f"📢 {txt}", parse_mode=ParseMode.HTML)
            except: pass
        await u.message.reply_text("✅ Duyuru tamamlandı.")

async def button_handler(u, c):
    q = u.callback_query; await q.answer()
    if q.data == 'st': await stats(u, c)
    elif q.data == 'dy': await q.message.reply_text("Duyuru için: /duyuru [mesaj]")
    else: await q.message.reply_text("📍 Sorgu için: /iftar şehir")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: handle_vakit(u,c,"iftar")))
    app.add_handler(CommandHandler("sahur", lambda u,c: handle_vakit(u,c,"sahur")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__": main()
