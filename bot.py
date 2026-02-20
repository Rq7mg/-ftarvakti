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
# 🛡️ SİSTEM KAYITLARI
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# ⚙️ AYARLAR VE ADMIN
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
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

async def save_chat_async(chat_id, chat_type):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": str(chat_type), "date": datetime.now().strftime("%d.%m.%Y %H:%M")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=4)
    except: pass

# =========================
# 🚀 ULTRA ŞEHİR MOTORU
# =========================
def get_prayertimes(city):
    if not city: return None
    try:
        # Gelişmiş Türkçe karakter ve yazım temizliği
        tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
        city_clean = city.lower().translate(tr_map).replace(" ", "-").strip()
        
        # Kesintisiz Global API (Key istemez)
        api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
        res = requests.get(api_url, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if "data" in data:
                return {"vakitler": data["data"]["timings"], "timezone": data["data"]["meta"]["timezone"], "yer": city.upper()}
        return None
    except: return None

def create_ultra_bar(sec, total):
    size = 12
    progress = min(1, max(0, 1 - (sec / total)))
    filled = int(size * progress)
    # Altın ve Mavi Elmas Temalı Bar
    bar = "🌕" * filled + "🌑" * (size - filled)
    return f"<code>{bar}</code>  <b>%{int(progress*100)}</b>"

# =========================
# 🎨 GÖRKEMLİ MESAJLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat_async(update.effective_chat.id, update.effective_chat.type)
    keyboard = [
        [InlineKeyboardButton("🌙 İftar", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Vakitler", callback_data='btn_vakit'), InlineKeyboardButton("⏳ Sayaç", callback_data='btn_sayac')],
        [InlineKeyboardButton("📜 Hadis", callback_data='btn_hadis'), InlineKeyboardButton("📊 Stats", callback_data='btn_stats')]
    ]
    welcome = (
        "⚜️ <b>RAMAZAN-I ŞERİF ELITE v16</b> ⚜️\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "Hoş geldiniz. Bu bot ile iftar ve sahur vakitlerini "
        "en yüksek görsel kalitede takip edebilirsiniz.\n\n"
        "📍 <b>Nasıl Sorgulanır?</b>\n"
        "└ <code>/iftar Bursa</code>\n"
        "└ <code>/sahur İstanbul</code>\n\n"
        "<i>İşlem seçmek için butonları kullanabilirsiniz:</i>"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("💡 <b>Örn:</b> <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)

    data = get_prayertimes(city)
    if not data:
        return await update.message.reply_text("❌ <b>Şehir Bulunamadı!</b>\nLütfen yazımı kontrol edin.", parse_mode=ParseMode.HTML)

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        bar = create_ultra_bar(sec, 57600 if mode=="Maghrib" else 28800)
        
        icon = "🌙" if mode == "Maghrib" else "🥣"
        title = "İFTAR VAKTİ" if mode == "Maghrib" else "SAHUR VAKTİ"
        
        mesaj = (
            f"✨ <b>{icon} {title} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b>  <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b>  <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<b>Doluluk Oranı:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"🕋 <i>Hayırlı Ramazanlar dileriz.</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except: pass

# =========================
# 🛠️ ADMIN VE YÖNETİM
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats = load_chats()
    await update.effective_message.reply_text(f"📊 <b>İstatistikler</b>\n┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n👤 Toplam Kullanıcı: <code>{len(chats)}</code>\n💎 Sürüm: <b>v16 Grand Sultan</b>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    if not text: return
    chats = load_chats()
    s, f = 0, 0
    prog = await update.message.reply_text("📢 Duyuru başladı...")
    for c in chats:
        try:
            await context.bot.send_message(chat_id=c["chat_id"], text=f"🔔 <b>DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05)
        except: f += 1
    await prog.edit_text(f"✅ <b>Bitti!</b>\nBaşarı: {s}\nHata: {f}")

# =========================
# 🕹️ BUTON YÖNETİCİSİ
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'btn_iftar': await query.message.reply_text("🍽️ <code>/iftar şehir</code> yazınız.")
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 <code>/sahur şehir</code> yazınız.")
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 Şehir bazlı tüm vakitler için <code>/iftar şehir</code> komutunu kullanabilirsiniz.")
    elif query.data == 'btn_stats': await stats(update, context)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan'a <b>{days}</b> gün kaldı.")
    elif query.data == 'btn_hadis':
        await query.message.reply_text("📜 <i>'Oruç tutunuz ki sıhhat bulasınız.'</i>")

# =========================
# 🚀 ANA MOTOR
# =========================
def main():
    if not TOKEN: return
    app = ApplicationBuilder().token(TOKEN).read_timeout(60).write_timeout(60).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat_async(u.effective_chat.id, u.effective_chat.type)), group=0)
    
    print("👑 v16 YÜKLENDİ. SULTANLAR GİBİ ÇALIŞIYOR.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
