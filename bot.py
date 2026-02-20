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
# ⚙️ AYARLAR
# =========================
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
            chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%Y-%m-%d %H:%M")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=4)
    except: pass

# =========================
# 🛠 GELİŞMİŞ ŞEHİR BULUCU (Güçlendirildi)
# =========================
def get_prayertimes(city):
    if not city or len(city) < 2: return None
    try:
        # Nominatim engellemesini aşmak için rastgele User-Agent
        random_ua = f"RamazanNavigator_{random.randint(100, 999)}_Bot"
        headers = {'User-Agent': random_ua, 'Accept-Language': 'tr-TR,tr;q=0.9'}
        
        # 1. Adım: Şehri Koordinata Çevir
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1&addressdetails=1"
        res = requests.get(geo_url, headers=headers, timeout=10).json()
        
        if not res: return None # Şehir bulunamazsa sessiz kal
        
        lat, lon = res[0]['lat'], res[0]['lon']
        yer_ismi = res[0].get('address', {}).get('province', city).capitalize()
        if not yer_ismi: yer_ismi = res[0].get('display_name', '').split(',')[0]

        # 2. Adım: Koordinat ile Vakitleri Al
        api_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        data = requests.get(api_url, timeout=10).json()
        
        if data["code"] != 200: return None
        
        return {
            "vakitler": data["data"]["timings"],
            "timezone": data["data"]["meta"]["timezone"],
            "yer": yer_ismi
        }
    except Exception as e:
        print(f"Hata: {e}")
        return None

def get_progress_bar(sec, total=57600):
    size = 12
    progress = min(1, max(0, 1 - (sec / total)))
    bar = "🟢" * int(size * progress) + "⚪" * (size - int(size * progress))
    return f"<code>{bar}</code> %{int(progress*100)}"

# =========================
# 🎮 KOMUTLAR (Async)
# =========================
async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        save_chat_sync(update.effective_chat.id, update.effective_chat.type)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await radar_handler(update, context)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Hadis", callback_data='btn_hadis'), InlineKeyboardButton("⏳ Sayaç", callback_data='btn_sayac')]
    ]
    msg = "<b>🌙 Ramazan Dijital Rehberi</b>\n\nŞehir ismini komutla beraber yazın.\nÖrn: <code>/iftar Bursa</code>"
    try: await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except: pass

async def iftar_sahur_engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city: return # Şehir yoksa sessiz kal (İsteğin üzerine)

    data = get_prayertimes(city)
    if not data: return # Şehir bulunamadıysa sessiz kal (İsteğin üzerine)

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        bar = get_progress_bar(sec, 57600 if mode=="Maghrib" else 28800)

        title = "🕌 İFTAR VAKTİ" if mode == "Maghrib" else "🌙 SAHUR VAKTİ"
        mesaj = (
            f"<b>{title} | {data['yer'].upper()}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{sec//3600} saat {(sec%3600)//60} dk</code>\n\n"
            f"{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except: pass

async def iftar_cmd(update, context): await iftar_sahur_engine(update, context, "Maghrib")
async def sahur_cmd(update, context): await iftar_sahur_engine(update, context, "Fajr")

async def vakit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else None
    if not city: return
    data = get_prayertimes(city)
    if not data: return
    v = data["vakitler"]
    msg = (f"<b>🕌 {data['yer'].upper()} VAKİTLERİ</b>\n┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
           f"🏙 İmsak: <code>{v['Fajr']}</code>\n☀️ Öğle: <code>{v['Dhuhr']}</code>\n"
           f"🌆 Akşam: <code>{v['Maghrib']}</code>\n┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈")
    try: await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except: pass

# =========================
# 🕹 ETKİLEŞİM VE ADMİN
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
        if query.data == 'btn_iftar': await query.message.reply_text("🍽 İftar için: <code>/iftar şehir</code>")
        elif query.data == 'btn_sahur': await query.message.reply_text("🥣 Sahur için: <code>/sahur şehir</code>")
        elif query.data == 'btn_vakit': await query.message.reply_text("🕌 Vakitler için: <code>/vakit şehir</code>")
        elif query.data == 'btn_hadis': 
            hadis = random.choice(["Oruç tutunuz ki sıhhat bulasınız.", "Sahurda bereket vardır."])
            await query.message.reply_text(f"📜 {hadis}")
        elif query.data == 'btn_sayac':
            days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
            await query.message.reply_text(f"⏳ Ramazan'a {max(0, days)} gün kaldı.")
    except: pass

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        try: await update.message.reply_text(f"📊 Kayıtlı Chat: {len(load_chats())}")
        except: pass

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return
    chats = load_chats()
    for c in chats:
        try:
            await context.bot.send_message(chat_id=c["chat_id"], text=text, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.05)
        except: pass

# =========================
# 🚀 ANA ÇALIŞTIRICI
# =========================
def main():
    if not TOKEN: return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd))
    app.add_handler(CommandHandler("sahur", sahur_cmd))
    app.add_handler(CommandHandler("vakit", vakit_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, radar_handler), group=0)
    print("🚀 RAMAZAN PRO v7 AKTİF!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
