import os
import json
import requests
import random
import asyncio
import pytz
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# 🛡️ GÜVENLİK VE LOG SİSTEMİ
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_chat_sync(chat_id, chat_type):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%d.%m.%Y")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=4)
    except: pass

# =========================
# 🎭 PREMİUM İÇERİKLER
# =========================
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Sahurun bereketi sabahın nurundadır.",
    "Ramazan ayı sabır, sabır ise cennettir.",
    "Oruçlu için iki sevinç vardır: İftar ve Mevla'ya kavuşma anı."
]
DUALAR = [
    "Allah'ım! Senin rızan için oruç tuttum, Senin rızkınla iftar ettim.",
    "Ey kalpleri evirip çeviren Allah! Kalbimi dinin üzere sabit kıl.",
    "Allah'ım! Sen affedicisin, kerem sahibisin, affı seversin; beni affet."
]
STILLER = ["🌙", "✨", "🕌", "💠", "🌟"]

# =========================
# 🚀 ÜST SEVİYE MOTOR (Fast API)
# =========================
def get_prayertimes(city):
    if not city or len(city) < 2: return None
    try:
        # Karakter temizleme
        tr_map = str.maketrans("çıığöşü", "ciigosu")
        city_clean = city.lower().translate(tr_map).strip()
        
        api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
        res = requests.get(api_url, timeout=8)
        if res.status_code == 200:
            data = res.json()
            return {"vakitler": data["data"]["timings"], "timezone": data["data"]["meta"]["timezone"], "yer": city.upper()}
        return None
    except: return None

def get_premium_bar(sec, total):
    size = 12
    progress = min(1, max(0, 1 - (sec / total)))
    filled = int(size * progress)
    # Elite Moon Phase Bar
    bar = "🌕" * filled + "🌑" * (size - filled)
    return f"<code>{bar}</code>  <b>%{int(progress*100)}</b>"

# =========================
# 🎮 ELİTE KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_sync(update.effective_chat.id, update.effective_chat.type)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar Vakti", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz Vakitleri", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Günün Hadisi", callback_data='btn_hadis'), InlineKeyboardButton("🤲 Günün Duası", callback_data='btn_dua')],
        [InlineKeyboardButton("⏳ Ramazan Sayacı", callback_data='btn_sayac'), InlineKeyboardButton("📊 İstatistik", callback_data='btn_stats')]
    ]
    welcome = (
        "✨ <b>HOŞ GELDİNİZ | RAMAZAN ELITE v12</b> ✨\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "On bir ayın sultanı Ramazan-ı Şerif'in bereketini "
        "en şık ve en hızlı şekilde takip edin.\n\n"
        "📍 <b>Nasıl Kullanılır?</b>\n"
        "└ <code>/iftar şehir</code> veya <code>/sahur şehir</code>\n\n"
        "<i>Aşağıdaki menüden dilediğinizi seçebilirsiniz:</i>"
    )
    try: await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except: pass

async def ramazan_engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        # Şehir girilmezse sessiz uyarı
        try: await update.message.reply_text("📍 Lütfen bir şehir ismi belirtin.\nÖrn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)
        except: pass
        return

    data = get_prayertimes(city)
    if not data:
        # Şehir bulunamazsa sessiz kal/uyar (isteğin üzerine)
        try: await update.message.reply_text("❌ Şehir veritabanında bulunamadı.", parse_mode=ParseMode.HTML)
        except: pass
        return

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        
        # Tasarım Kartı
        title = "🌙 İFTARA KALAN SÜRE" if mode == "Maghrib" else "🥣 SAHURA KALAN SÜRE"
        bar = get_premium_bar(sec, 57600 if mode=="Maghrib" else 28800)
        icon = random.choice(STILLER)

        mesaj = (
            f"{icon} <b>{title}</b> {icon}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"🏢 <b>Şehir:</b> <code>{data['yer']}</code>\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<b>İlerleme:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except: pass

async def vakit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else None
    if not city: return
    data = get_prayertimes(city)
    if not data: return
    v = data["vakitler"]
    msg = (
        f"🕌 <b>{data['yer']} VAKİTLERİ</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🏙 İmsak:  <code>{v['Fajr']}</code>\n"
        f"🌅 Güneş:  <code>{v['Sunrise']}</code>\n"
        f"☀️ Öğle:   <code>{v['Dhuhr']}</code>\n"
        f"🌓 İkindi: <code>{v['Asr']}</code>\n"
        f"🌆 Akşam:  <code>{v['Maghrib']}</code>\n"
        f"🌃 Yatsı:  <code>{v['Isha']}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
    )
    try: await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except: pass

# =========================
# 🕹 ETKİLEŞİM VE ADMİN
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'btn_iftar': await query.message.reply_text("🍽 <code>/iftar şehir</code> yazınız.")
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 <code>/sahur şehir</code> yazınız.")
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 <code>/vakit şehir</code> yazınız.")
    elif query.data == 'btn_hadis': await query.message.reply_text(f"📜 <b>Günün Hadisi:</b>\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_dua': await query.message.reply_text(f"🤲 <b>Günün Duası:</b>\n<i>{random.choice(DUALAR)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan-ı Şerif'e <b>{max(0, days)}</b> gün kaldı. ✨")
    elif query.data == 'btn_stats':
        await query.message.reply_text(f"📊 <b>Toplam Kullanıcı:</b> <code>{len(load_chats())}</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return
    chats = load_chats()
    s, f = 0, 0
    for c in chats:
        try:
            await context.bot.send_message(chat_id=c["chat_id"], text=f"📢 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await update.message.reply_text(f"✅ Tamamlandı. (Başarı: {s}, Hata: {f})")

# =========================
# 🚀 ANA ÇALIŞTIRICI (Zırhlı)
# =========================
def main():
    if not TOKEN: return
    # Heroku stabilite ayarları
    app = ApplicationBuilder().token(TOKEN).read_timeout(40).write_timeout(40).connect_timeout(40).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: ramazan_engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: ramazan_engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("vakit", vakit_cmd))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat_sync(u.effective_chat.id, u.effective_chat.type)), group=0)

    print("🚀 RAMAZAN ELITE v12 AKTİF! GÖRKEMLİ AÇILIŞ YAPILDI.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
