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
# 💾 VERİ DEPOLAMA (JSON)
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_chat(chat_id, chat_type):
    chats = load_chats()
    if not any(c['chat_id'] == chat_id for c in chats):
        chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%Y-%m-%d")})
        with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f, indent=4)

# =========================
# 📚 ZENGİN İÇERİK HAVUZU
# =========================
HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız. (Taberânî)",
    "Sahur yapın, zira sahurda bereket vardır. (Müslim)",
    "Gerçek oruç, sadece yiyip içmeyi değil, boş ve hayâsızca sözleri de terk etmektir.",
    "Ramazan ayı sabır ayıdır; sabrın sevabı ise cennetir."
]

DUALAR = [
    "Allahümme leke sumtü ve bike âmentü ve aleyke tevekkeltü ve alâ rızkıke eftartü.",
    "Allah'ım! Sen affedicisin, affı seversin, beni de affet.",
    "Rabbim! Bu mübarek ayda yaptığımız ibadetleri ve tuttuğumuz oruçları kabul eyle."
]

SAGLIK_NOTLARI = [
    "💧 Sahurda su tüketimini zamana yay, aniden yüklenme.",
    "🥣 İftarı bir kase çorba ile açıp 15 dakika ara vermek sindirimi kolaylaştırır.",
    "🍳 Sahurda protein ağırlıklı (yumurta, peynir) beslenmek tok tutar.",
    "🚶‍♂️ İftardan 1 saat sonra hafif tempolu yürüyüş yapmak metabolizmayı canlandırır."
]

# =========================
# 🛠 AKILLI MOTORLAR (API & Hesaplama)
# =========================
def get_prayertimes(city):
    try:
        headers = {'User-Agent': 'RamazanEliteBot/v2'}
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
    return f"{bar} %{int(progress*100)}"

# =========================
# 🎮 KOMUT FONKSİYONLARI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat.id, update.effective_chat.type)
    keyboard = [
        [InlineKeyboardButton("🍽 İftar", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz Vakitleri", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Hadis", callback_data='btn_hadis'), InlineKeyboardButton("🤲 Dua", callback_data='btn_dua')],
        [InlineKeyboardButton("🩺 Sağlık", callback_data='btn_saglik'), InlineKeyboardButton("⏳ Sayaç", callback_data='btn_sayac')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        "<b>🌙 Ramazan-ı Şerif Dijital Rehberi</b>\n\n"
        "Hoş geldin gardaş! Bu bot ile iftar vaktinden hadislere, sağlık önerilerinden sayaçlara kadar her şeye ulaşabilirsin.\n\n"
        "⚡ <b>Hızlı Erişim:</b> <code>/iftar şehir</code> veya <code>/sahur şehir</code>"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def iftar_sahur_engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text(f"📍 Lütfen şehir yazın.\nÖrn: <code>/{'iftar' if mode=='Maghrib' else 'sahur'} İstanbul</code>", parse_mode=ParseMode.HTML)
    
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

    mesaj = (
        f"<b>{'🕌 İFTAR VAKTİ' if mode=='Maghrib' else '🌙 SAHUR VAKTİ'} | {data['yer'].upper()}</b>\n"
        f"📅 <code>{datetime.now().strftime('%d %B %Y')}</code>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"⏰ <b>Ezan:</b> <code>{target_str}</code>\n"
        f"⏳ <b>Kalan:</b> <code>{sec//3600} saat {(sec%3600)//60} dk</code>\n\n"
        f"<b>İlerleme:</b> {bar}\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"✨ <i>{random.choice(HADISLER if mode=='Fajr' else DUALAR)}</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def vakit_goster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = " ".join(context.args) if context.args else None
    if not city: return await update.message.reply_text("📍 Örn: <code>/vakit Bursa</code>", parse_mode=ParseMode.HTML)
    
    data = get_prayertimes(city)
    if not data: return await update.message.reply_text("❌ Şehir bulunamadı.")
    v = data["vakitler"]
    
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
# 🕹 BUTON YAKALAYICI
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'btn_iftar': await query.message.reply_text("🍽 İftar vakti için <code>/iftar şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 Sahur vakti için <code>/sahur şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 Namaz vakitleri için <code>/vakit şehir</code> yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_hadis': await query.message.reply_text(f"📜 <b>HADİS-İ ŞERİF</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_dua': await query.message.reply_text(f"🤲 <b>GÜNÜN DUASI</b>\n\n<i>{random.choice(DUALAR)}</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_saglik': await query.message.reply_text(f"🩺 <b>SAĞLIK ÖNERİSİ</b>\n\n{random.choice(SAGLIK_NOTLARI)}", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan'ın başlamasına <b>{max(0, days)} gün</b> kaldı.", parse_mode=ParseMode.HTML)

# =========================
# 🛡 ADMİN PANELİ (Stats & Duyuru)
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    chats = load_chats()
    await update.message.reply_text(f"📊 <b>İSTATİSTİK</b>\n\n👥 Toplam Kayıt: <code>{len(chats)}</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return await update.message.reply_text("❌ Mesaj girmedin.")
    
    chats = load_chats()
    success, fail = 0, 0
    progress_msg = await update.message.reply_text(f"🚀 {len(chats)} kişiye gönderiliyor...")
    
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except: fail += 1
    await progress_msg.edit_text(f"✅ <b>Bitti!</b>\n\n📢 Başarılı: {success}\n❌ Hatalı: {fail}", parse_mode=ParseMode.HTML)

# =========================
# 🚀 ANA ÇALIŞTIRICI
# =========================
def main():
    if not TOKEN: return print("HATA: TOKEN BULUNAMADI!")
    app = ApplicationBuilder().token(TOKEN).build()

    # Radar (Tüm mesajları yakalayıp kaydeder)
    app.add_handler(MessageHandler(filters.ALL, lambda u, c: save_chat(u.effective_chat.id, u.effective_chat.type)), group=0)

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: iftar_sahur_engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: iftar_sahur_engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("vakit", vakit_goster))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    # Callback
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🚀 BOT MARŞA BASTI! RAMAZAN PRO AKTİF.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
