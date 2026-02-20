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
# ⚙️ AYARLAR (Config)
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
    chats = load_chats()
    if not any(c['chat_id'] == chat_id for c in chats):
        chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%Y-%m-%d")})
        with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=4)

# =========================
# 🛠 AKILLI MOTORLAR
# =========================
def get_prayertimes(city):
    try:
        headers = {'User-Agent': 'RamazanEliteBot/v3'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        res = requests.get(geo_url, headers=headers, timeout=10).json()
        if not res: return None
        lat, lon = res[0]['lat'], res[0]['lon']
        yer = res[0]['display_name'].split(",")[0]
        api_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        data = requests.get(api_url, timeout=10).json()
        return {"vakitler": data["data"]["timings"], "timezone": data["data"]["meta"]["timezone"], "yer": yer}
    except: return None

def get_progress_bar(sec, total=57600):
    size = 12
    progress = min(1, max(0, 1 - (sec / total)))
    filled = int(size * progress)
    bar = "🟢" * filled + "⚪" * (size - filled)
    return f"<code>{bar}</code> %{int(progress*100)}"

# =========================
# 🎮 ASENKRON KOMUTLAR
# =========================

async def radar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Her etkileşimde chat'i kaydeder."""
    if update.effective_chat:
        save_chat_sync(update.effective_chat.id, update.effective_chat.type)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await radar_handler(update, context)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz Vakitleri", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Hadis", callback_data='btn_hadis'), InlineKeyboardButton("🤲 Dua", callback_data='btn_dua')],
        [InlineKeyboardButton("🩺 Sağlık", callback_data='btn_saglik'), InlineKeyboardButton("⏳ Sayaç", callback_data='btn_sayac')]
    ]
    msg = (
        "<b>🌙 Ramazan-ı Şerif Dijital Rehberi</b>\n\n"
        "Hoş geldin gardaş! Senin için hazırlandım. Aşağıdaki butonları kullanabilir veya şehir belirterek komut verebilirsin.\n\n"
        "⚡ <b>Hızlı Komutlar:</b>\n"
        "├ <code>/iftar şehir</code>\n"
        "└ <code>/sahur şehir</code>"
    )
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def iftar_sahur_engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        txt = "İftar" if mode == "Maghrib" else "Sahur"
        return await update.message.reply_text(f"📍 Lütfen şehir yazın.\nÖrn: <code>/{txt.lower()} İstanbul</code>", parse_mode=ParseMode.HTML)
    
    data = get_prayertimes(city)
    if not data: return await update.message.reply_text("❌ Şehir bulunamadı.")

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
        f"⏰ <b>Ezan:</b> <code>{target_str}</code>\n"
        f"⏳ <b>Kalan:</b> <code>{sec//3600} saat {(sec%3600)//60} dk</code>\n\n"
        f"<b>İlerleme:</b>\n{bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>Hayırlı ibadetler dilerim.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# Lambda yerine geçen async fonksiyonlar
async def iftar_cmd(update, context): await iftar_sahur_engine(update, context, "Maghrib")
async def sahur_cmd(update, context): await iftar_sahur_engine(update, context, "Fajr")

async def vakit_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else None
    if not city: return await update.message.reply_text("📍 Örn: <code>/vakit Ankara</code>", parse_mode=ParseMode.HTML)
    
    data = get_prayertimes(city)
    if not data: return await update.message.reply_text("❌ Şehir bulunamadı.")
    v = data["data"]["timings"] if "data" in data else data["vakitler"]
    
    msg = (
        f"<b>🕌 {data['yer'].upper()} VAKİTLERİ</b>\n"
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
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# =========================
# 🕹 ETKİLEŞİM YÖNETİMİ
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'btn_iftar': await query.message.reply_text("🍽 İftar için: <code>/iftar şehir</code>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 Sahur için: <code>/sahur şehir</code>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 Vakitler için: <code>/vakit şehir</code>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_hadis': await query.message.reply_text("📜 <i>\"Oruç tutunuz ki sıhhat bulasınız.\"</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_dua': await query.message.reply_text("🤲 <i>\"Allah'ım! Sen affedicisin, affı seversin, beni de affet.\"</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan'a <b>{max(0, days)}</b> gün kaldı.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_saglik': await query.message.reply_text("🩺 Sahurda yumurta yemek seni tok tutar!", parse_mode=ParseMode.HTML)

# =========================
# 🛡 ADMİN
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text(f"📊 <b>Toplam Kayıt:</b> <code>{len(load_chats())}</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return await update.message.reply_text("❌ Mesaj yok.")
    
    chats = load_chats()
    success, fail = 0, 0
    m = await update.message.reply_text(f"🚀 {len(chats)} adrese gönderiliyor...")
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await m.edit_text(f"✅ <b>Bitti!</b>\n\n📢 Başarılı: {success}\n❌ Hatalı: {fail}", parse_mode=ParseMode.HTML)

# =========================
# 🚀 ANA ÇALIŞTIRICI
# =========================
def main():
    if not TOKEN: return print("HATA: TOKEN YOK!")
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar_cmd)) # Hata çözüldü
    app.add_handler(CommandHandler("sahur", sahur_cmd)) # Hata çözüldü
    app.add_handler(CommandHandler("vakit", vakit_goster))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Radar (Filtreleme grubu 0)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, radar_handler), group=0)

    print("🚀 RAMAZAN PRO MAX V3 AKTİF!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
