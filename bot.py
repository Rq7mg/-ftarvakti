import os
import json
import httpx
import asyncio
import pytz
import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler
)

# =========================
# 🛡️ AYARLAR VE LOG SİSTEMİ
# =========================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, onun sevabı kadar sevap kazanır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu vakit.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur.",
    "Beş vakit namaz ve Cuma namazı, büyük günahlardan kaçınıldığı sürece aradaki günahlara kefarettir."
]

# =========================
# 💾 VERİ TABANI YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_chat(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "join_date": datetime.now().strftime("%d.%m.%Y")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=4)
    except Exception as e:
        logger.error(f"Dosya kayıt hatası: {e}")

# =========================
# 🚀 HIZLI ŞEHİR MOTORU
# =========================
async def get_prayertimes(city_input):
    if not city_input: return None
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("data"):
                    return {
                        "vakitler": data["data"]["timings"], 
                        "timezone": data["data"]["meta"]["timezone"], 
                        "yer": city_input.upper()
                    }
        except Exception as e:
            logger.error(f"API Hatası: {e}")
            return None
    return None

# =========================
# 🎭 ANA KOMUT FONKSİYONLARI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("🌙 İftar", callback_data='btn_i'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_s')],
        [InlineKeyboardButton("📜 Günün Hadisi", callback_data='btn_h')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚜️ <b>RAMAZAN ELITE v25 KONTROL PANELİ</b> ⚜️\n\n"
        "Şehir ismini yazarak vakitleri öğrenebilirsiniz.\n"
        "Örn: <code>/iftar Ankara</code>\n\n"
        "Aşağıdaki butonlarla hızlı işlem yapabilirsiniz:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_hesapla(update, context, "Maghrib")

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vakit_hesapla(update, context, "Fajr")

async def vakit_hesapla(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text("📍 Lütfen bir şehir adı girin.\nÖrn: <code>/iftar Bursa</code>", parse_mode=ParseMode.HTML)
        return

    data = await get_prayertimes(city)
    if not data:
        await update.message.reply_text(f"❌ <b>'{city}'</b> şehri bulunamadı. Lütfen Türkçe karakterlere dikkat ederek tekrar deneyin.")
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
        
        # Görsel İlerleme Barı
        progress = min(1, max(0, 1 - (sec / 57600)))
        bar_len = 12
        filled = int(bar_len * progress)
        bar = "🌕" * filled + "🌑" * (bar_len - filled)

        label = "İFTAR" if mode == "Maghrib" else "SAHUR"
        mesaj = (
            f"✨ <b>{label} VAKTİ | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b>  <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b>  <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(progress*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📜 <i>{random.choice(HADISLER)}</i>"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=mesaj, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Hesaplama hatası: {e}")
        await update.message.reply_text("⚠️ Vakit hesaplanırken bir hata oluştu.")

# =========================
# 🛠️ ADMIN VE ÖZEL ARAÇLAR
# =========================
async def hadis_ver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    secilen = random.choice(HADISLER)
    await update.message.reply_text(f"📜 <b>Günün Hadisi:</b>\n\n<i>{secilen}</i>", parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    users = load_chats()
    await update.message.reply_text(f"📊 <b>Toplam Kullanıcı Sayısı:</b> <code>{len(users)}</code>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("💡 Kullanım: `/duyuru Merhaba Millet!`")
        return
    
    chats = load_chats()
    success, fail = 0, 0
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    await update.message.reply_text(f"✅ Duyuru tamamlandı.\nBaşarılı: {success}\nHatalı: {fail}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'btn_i':
        await query.message.reply_text("🍽 Lütfen <code>/iftar ŞehirAdı</code> şeklinde yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_s':
        await query.message.reply_text("🥣 Lütfen <code>/sahur ŞehirAdı</code> şeklinde yazın.", parse_mode=ParseMode.HTML)
    elif query.data == 'btn_h':
        await query.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def track_everything(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat:
        save_chat(update.effective_chat.id)

# =========================
# 🚀 BOTU BAŞLAT
# =========================
def main():
    if not TOKEN:
        print("❌ HATA: TOKEN bulunamadı!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # Komut Kayıtları
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("hadis", hadis_ver))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    
    # Buton ve Mesaj Takibi
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_everything))

    print("🚀 RAMAZAN ELITE v25 AKTİF! (Hatalar Giderildi)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
