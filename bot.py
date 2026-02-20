import os
import json
import requests
import random
import asyncio
import pytz
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR & RAKAMLAR
# =========================
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

# =========================
# 💾 VERİ DEPOLAMA
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
# 📚 ZENGİN İÇERİK HAVUZU
# =========================
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. (Taberânî)",
    "Sahur yapın, zira sahurda bereket vardır. (Müslim)",
    "Ramazan ayı sabır ayıdır; sabrın sevabı ise cennetir.",
    "Cennetin bir kapısı vardır, adı 'Reyyân'dır. Oradan sadece oruçlular girer."
]

DUALAR = [
    "Allah'ım! Senin rızan için oruç tuttum, senin rızkınla iftar ettim.",
    "Rabbimiz! Bize dünyada da iyilik ver, ahirette de iyilik ver.",
    "Allah'ım! Sen affedicisin, affetmeyi seversin, beni de affet."
]

SAGLIK_NOTLARI = [
    "🥣 İftarı bir kase çorba ile açıp 15 dakika ara vermek sindirimi rahatlatır.",
    "💧 Sahurda su tüketimini zamana yaymak gün boyu hidrasyon sağlar.",
    "🍳 Sahurda yumurta gibi proteinler tüketmek tokluk süresini uzatır."
]

# =========================
# 🚀 GELİŞMİŞ GÖRSEL MOTOR
# =========================
def get_prayertimes(city):
    if not city or len(city) < 2: return None
    try:
        city_clean = city.strip().lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
        api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
        res = requests.get(api_url, timeout=10).json()
        if res["code"] == 200:
            return {"vakitler": res["data"]["timings"], "timezone": res["data"]["meta"]["timezone"], "yer": city.upper()}
        return None
    except: return None

def create_progress_bar(sec, total=57600):
    size = 10
    progress = min(1, max(0, 1 - (sec / total)))
    filled = int(size * progress)
    # Daha şık ay evreleri temalı bar
    bar = "🌕" * filled + "🌑" * (size - filled)
    return f"{bar}  <b>%{int(progress*100)}</b>"

# =========================
# 🎮 ANA FONKSİYONLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat_sync(update.effective_chat.id, update.effective_chat.type)
    
    keyboard = [
        [InlineKeyboardButton("🍽 İftar Vakti", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz Vakitleri", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Hadis-i Şerif", callback_data='btn_hadis'), InlineKeyboardButton("🤲 Günün Duası", callback_data='btn_dua')],
        [InlineKeyboardButton("🩺 Sağlık Rehberi", callback_data='btn_saglik'), InlineKeyboardButton("⏳ Ramazan Sayacı", callback_data='btn_sayac')]
    ]
    
    welcome_text = (
        "<b>🌙 HAYIRLI RAMAZANLAR! 🌙</b>\n\n"
        "Gönüllere huzur, sofralara bereket getiren Ramazan-ı Şerif'te dijital rehberin yanına geldi! ✨\n\n"
        "🔹 <b>Şehir belirterek hızlı erişim:</b>\n"
        "└ <code>/iftar Ankara</code> veya <code>/sahur İstanbul</code>\n\n"
        "<i>Aşağıdaki menüden merak ettiğin bilgiye ulaşabilirsin:</i>"
    )
    
    try:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except: pass

async def ramazan_engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city: return # Sessiz kalma isteği

    data = get_prayertimes(city)
    if not data: return # Şehir bulunamazsa sessiz kal

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        bar = create_progress_bar(sec, 57600 if mode=="Maghrib" else 28800)

        # Görsel Tasarım Kartı
        header = "✨ İFTARA NE KADAR KALDI?" if mode == "Maghrib" else "✨ SAHURA NE KADAR KALDI?"
        footer = random.choice(DUALAR) if mode == "Maghrib" else random.choice(HADISLER)
        
        mesaj = (
            f"<b>{header}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📍 <b>Bölge:</b> <code>{data['yer']}</code>\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⌛ <b>Kalan:</b> <code>{sec//3600} saat {(sec%3600)//60} dk</code>\n\n"
            f"<b>Doluluk:</b> {bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{footer}</i>"
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
        f"<b>🕌 {data['yer']} NAMAZ VAKİTLERİ</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"🏙 <b>İmsak:</b>  <code>{v['Fajr']}</code>\n"
        f"🌅 <b>Güneş:</b>  <code>{v['Sunrise']}</code>\n"
        f"☀️ <b>Öğle:</b>   <code>{v['Dhuhr']}</code>\n"
        f"🌓 <b>İkindi:</b> <code>{v['Asr']}</code>\n"
        f"🌆 <b>Akşam:</b>  <code>{v['Maghrib']}</code>\n"
        f"🌃 <b>Yatsı:</b>  <code>{v['Isha']}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"<i>Dualarınız kabul olsun.</i>"
    )
    try: await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except: pass

# =========================
# 🕹 ETKİLEŞİM YÖNETİCİSİ
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'btn_iftar': await query.message.reply_text("🍽 <b>İftar Vakti</b> için <code>/iftar şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 <b>Sahur Vakti</b> için <code>/sahur şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 <b>Tüm vakitler</b> için <code>/vakit şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_hadis': await query.message.reply_text(f"📜 <b>GÜNÜN HADİSİ</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_dua': await query.message.reply_text(f"🤲 <b>GÜNÜN DUASI</b>\n\n<i>{random.choice(DUALAR)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_saglik': await query.message.reply_text(f"🩺 <b>SAĞLIK ÖNERİSİ</b>\n\n{random.choice(SAGLIK_NOTLARI)}", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan-ı Şerif'in başlamasına <b>{max(0, days)} gün</b> kaldı. Hayırla gelsin! ✨", parse_mode=ParseMode.HTML)

# =========================
# 🛡 ADMİN & RADAR
# =========================
async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        save_chat_sync(update.effective_chat.id, update.effective_chat.type)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(f"📊 <b>Toplam Gönül Bağı:</b> <code>{len(load_chats())} kişi</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return
    chats = load_chats()
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=f"📢 <b>RAMAZAN DUYURUSU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except: pass

# =========================
# 🚀 ANA ÇALIŞTIRICI
# =========================
def main():
    if not TOKEN: return
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: ramazan_engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: ramazan_engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("vakit", vakit_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, radar_handler), group=0)

    print("🚀 RAMAZAN ELITE v10 YÜKLENDİ! GÖRSELLİK AKTİF.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
