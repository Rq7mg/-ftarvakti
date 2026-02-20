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
# 🛡️ LOG SİSTEMİ
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# ⚙️ AYARLAR
# =========================
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208] # Senin ve diğer adminin ID'si
CHATS_FILE = "chats.json"

# =========================
# 💾 VERİ YÖNETİMİ (Kusursuz)
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
            chats.append({
                "chat_id": chat_id, 
                "type": str(chat_type), 
                "date": datetime.now().strftime("%d.%m.%Y %H:%M")
            })
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=4)
            logger.info(f"💾 Yeni Kullanıcı: {chat_id}")
    except Exception as e:
        logger.error(f"Kayıt Hatası: {e}")

# =========================
# 🚀 GELİŞMİŞ API MOTORU
# =========================
def get_prayertimes(city):
    if not city or len(city) < 2: return None
    try:
        # Türkçe karakter zırhı (Şehir bulunamama sorununu çözer)
        tr_map = str.maketrans("çıığöşü", "ciigosu")
        city_clean = city.lower().translate(tr_map).strip()
        
        api_url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
        res = requests.get(api_url, timeout=12)
        if res.status_code == 200:
            data = res.json()
            return {
                "vakitler": data["data"]["timings"], 
                "timezone": data["data"]["meta"]["timezone"], 
                "yer": city.upper()
            }
        return None
    except: return None

def create_premium_bar(sec, total):
    size = 12
    progress = min(1, max(0, 1 - (sec / total)))
    filled = int(size * progress)
    bar = "🔷" * filled + "💠" * (size - filled)
    return f"<code>{bar}</code>  <b>%{int(progress*100)}</b>"

# =========================
# 🎮 KULLANICI KOMUTLARI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat_async(update.effective_chat.id, update.effective_chat.type)
    
    keyboard = [
        [InlineKeyboardButton("🍽️ İftar Vakti", callback_data='btn_iftar'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='btn_sahur')],
        [InlineKeyboardButton("🕌 Namaz Vakitleri", callback_data='btn_vakit')],
        [InlineKeyboardButton("📜 Günün Hadisi", callback_data='btn_hadis'), InlineKeyboardButton("🤲 Günün Duası", callback_data='btn_dua')],
        [InlineKeyboardButton("⏳ Ramazan Sayacı", callback_data='btn_sayac'), InlineKeyboardButton("📊 İstatistik", callback_data='btn_stats')]
    ]
    
    welcome = (
        "✨ <b>RAMAZAN-I ŞERİF ELİTE v14</b> ✨\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "Hoş geldiniz! En doğru vakitler ve en şık görsellerle "
        "Ramazan boyunca hizmetinizdeyiz.\n\n"
        "📍 <b>Hızlı Sorgu:</b>\n"
        "└ <code>/iftar Bursa</code>\n"
        "└ <code>/sahur İstanbul</code>\n"
        "└ <code>/vakit Ankara</code>"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("⚠️ Lütfen bir şehir belirtin.\nÖrn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)

    data = get_prayertimes(city)
    if not data:
        return await update.message.reply_text("❌ Şehir bulunamadı! Lütfen doğru yazdığınızdan emin olun.")

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        
        if now >= target: target += timedelta(days=1)
        
        diff = target - now
        sec = int(diff.total_seconds())
        bar = create_premium_bar(sec, 57600 if mode=="Maghrib" else 28800)
        
        title = "🌙 İFTAR VAKTİ" if mode == "Maghrib" else "🥣 SAHUR VAKTİ"
        mesaj = (
            f"✨ <b>{title} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<b>Doluluk Oranı:</b>\n{bar}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>Oruç tutunuz ki sıhhat bulasınız.</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Hata: {e}")

# =========================
# 🛠️ ADMIN KOMUTLARI (Full Fonksiyonel)
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hem butonla hem komutla çalışır, admin kontrolü yapılır
    user_id = update.effective_user.id
    chats = load_chats()
    
    status_msg = (
        "📊 <b>BOT İSTATİSTİKLERİ</b>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"👤 <b>Toplam Kullanıcı:</b> <code>{len(chats)}</code>\n"
        f"🛡️ <b>Admin Yetkisi:</b> {'✅ Var' if user_id in ADMIN_IDS else '❌ Yok'}\n"
        f"🚀 <b>Sürüm:</b> <code>v14 Elite Final</code>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈"
    )
    await update.effective_message.reply_text(status_msg, parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("⛔ Bu komut sadece adminler içindir.")

    # Mesaj metnini al (ya yanıttan ya da komuttan sonraki metinden)
    content = ""
    if update.message.reply_to_message:
        content = update.message.reply_to_message.text
    else:
        content = " ".join(context.args)

    if not content:
        return await update.message.reply_text("⚠️ Duyuru içeriği boş olamaz!\nKullanım: <code>/duyuru Merhaba millet!</code>", parse_mode=ParseMode.HTML)

    chats = load_chats()
    success, fail = 0, 0
    progress_msg = await update.message.reply_text(f"📢 Duyuru gönderiliyor... (0/{len(chats)})")

    for c in chats:
        try:
            await context.bot.send_message(
                chat_id=c["chat_id"], 
                text=f"🔔 <b>GÜNÜN DUYURUSU</b>\n\n{content}\n\n🌙 <i>Hayırlı Ramazanlar</i>", 
                parse_mode=ParseMode.HTML
            )
            success += 1
            await asyncio.sleep(0.05) # Rate limit koruması
        except:
            fail += 1
    
    await progress_msg.edit_text(f"✅ <b>Duyuru Tamamlandı!</b>\n\n🟢 Başarılı: {success}\n🔴 Hatalı: {fail}", parse_mode=ParseMode.HTML)

# =========================
# 🕹️ BUTON YÖNETİMİ
# =========================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'btn_iftar': await query.message.reply_text("🍽️ <code>/iftar şehir</code> yazın.")
    elif query.data == 'btn_sahur': await query.message.reply_text("🥣 <code>/sahur şehir</code> yazın.")
    elif query.data == 'btn_vakit': await query.message.reply_text("🕌 <code>/vakit şehir</code> yazın.")
    elif query.data == 'btn_stats': await stats(update, context)
    elif query.data == 'btn_hadis': 
        await query.message.reply_text("📜 <i>Sahurun bereketi sabahın nurundadır. ✨</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_dua': 
        await query.message.reply_text("🤲 <i>Allah'ım! Senin rızan için oruç tuttum. 🍽️</i>", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_sayac':
        days = (datetime(2026, 2, 19).date() - datetime.now().date()).days
        await query.message.reply_text(f"⏳ Ramazan'a <b>{max(0, days)}</b> gün kaldı. ✨", parse_mode=ParseMode.HTML)

# =========================
# 🚀 BOTU BAŞLAT
# =========================
def main():
    if not TOKEN: return
    app = ApplicationBuilder().token(TOKEN).read_timeout(60).write_timeout(60).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("vakit", lambda u, c: engine(u, c, "Dhuhr"))) # Örnek vakit
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Radar: Mesaj atan herkesi kaydeder
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat_async(u.effective_chat.id, u.effective_chat.type)), group=0)

    print("🚀 RAMAZAN ELITE v14 YÜKLENDİ! HER ŞEY TAMAM.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
