import os
import json
import requests
from datetime import datetime, timedelta
import pytz
import random
import asyncio
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# =========================
# AYARLAR (Config)
# =========================
TOKEN = os.environ.get("TOKEN")
ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"
HADIS_DOSYA = "hadisler.json"
tz = pytz.timezone("Europe/Istanbul")

# =========================
# 1. VERİ YÖNETİMİ
# =========================

def load_json(dosya):
    try:
        if os.path.exists(dosya):
            with open(dosya, "r", encoding="utf-8") as f:
                return json.load(f)
    except: return []
    return []

HADISLER = load_json(HADIS_DOSYA)

def get_all_chats():
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def kaydet_chat_id(chat_id, chat_type):
    try:
        chats = get_all_chats()
        if not any(c["chat_id"] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": chat_type})
            with open(CHAT_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f)
    except: pass

# =========================
# 2. CANLI VAKİT ÇEKME (API)
# =========================

def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower().strip()

def get_prayertimes(city):
    """
    Diyanet uyumlu Aladhan API kullanılır.
    """
    try:
        city_norm = normalize(city)
        # API 13. metodu (Diyanet) kullanarak veriyi çeker
        url = f"https://api.aladhan.com/v1/timingsByCity?city={city_norm}&country=Turkey&method=13"
        
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return None
            
        data = r.json()
        if data and "data" in data:
            return data["data"]["timings"]
        return None
    except Exception as e:
        print(f"API Mevzusu Patladı: {e}")
        return None

def time_until(vakit_str):
    if not vakit_str: return 0, 0, "--:--"
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    
    if now >= vakit_time:
        vakit_time += timedelta(days=1)
        
    delta = vakit_time - now
    total_seconds = int(delta.total_seconds())
    return total_seconds // 3600, (total_seconds % 3600) // 60, vakit_time.strftime("%H:%M")

# =========================
# 3. ANKARA ŞİVELİ KOMUTLAR
# =========================

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ **La bebe hangi şehri soruyon?**\nÖrn: `/iftar ankara` yaz hele.", parse_mode=ParseMode.HTML)
        return
    
    city = " ".join(context.args)
    timings = get_prayertimes(city)
    
    if not timings:
        await update.message.reply_text(f"❌ **Bak hele, '{city}' diye bi yer bulamadım.**\nHaritayı mı yedin gardaş? Düzgün yaz!", parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Maghrib"])
    mesaj = (
        f"🕌 <b>İFTAR VAKTİ | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"🕓 <b>Akşam Ezanı:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"🤲 <b>İftar Duası:</b>\n"
        f"<i>'Allah'ım senin rızan için oruç tuttum, senin rızkınla orucumu açıyorum.'</i>\n\n"
        f"✨ <b>Hayırlı İftarlar Gardaşım...</b>\n"
        f"Çömelin sofraya, ezana az kaldı! 🥖"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ **Sahur vaktini merak ediyon ama şehir yazmıyon...**", parse_mode=ParseMode.HTML)
        return
        
    city = " ".join(context.args)
    timings = get_prayertimes(city)
    
    if not timings:
        await update.message.reply_text("❌ **Vakitleri çekemedim gardaş, sistem vites boşta kaldı.**", parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Fajr"])
    mesaj = (
        f"🌌 <b>SAHUR (İMSAK) | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"📢 <b>İmsak Vakti:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"💡 <b>Niyet:</b>\n"
        f"<i>'Niyet ettim Allah rızası için bugünkü Ramazan orucunu tutmaya.'</i>\n\n"
        f"🤲 <b>Bereketli Sahurlar La Bebe.</b>\n"
        f"Suyu kana kana iç, sonra yanarsın! 💧"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    # 2026 Ramazan Başlangıcı: 19 Şubat
    start_date = datetime(2026, 2, 19, tzinfo=tz).date()
    end_date = datetime(2026, 3, 19, tzinfo=tz).date()
    
    if now < start_date:
        kalan = (start_date - now).days
        mesaj = f"⏳ <b>RAMAZAN'A KAVUŞMAYA</b>\n\n🌙 On bir ayın sultanına son <b>{kalan} gün</b> kaldı gardaş!"
    elif now > end_date:
        mesaj = "👋 <b>Elveda Ya Şehr-i Ramazan...</b>\n\nRabbim tekrarına kavuştursun la bebe."
    else:
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN-I ŞERİF</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
            f"🗓 Bugün Ramazan'ın <b>{gun}. günü</b>.\n\n"
            f"<i>Rabbim oruçlarınızı makbul eylesin, dualarda bizi unutmayın.</i>"
        )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    mesaj = (
        "<b>🌙 Hoş Geldin Gardaş!</b>\n\n"
        "Ramazan rehberin emrine amade. Şehir yaz, vakti kap!\n\n"
        "🍽 /iftar <code>şehir</code>\n"
        "🥣 /sahur <code>şehir</code>\n"
        "📜 /hadis\n"
        "📅 /ramazan"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("📜 <i>Sabır müminin zırhıdır gardaş.</i>")
        return
    secilen = random.choice(HADISLER)
    await update.message.reply_text(f"📜 <b>GÜNÜN HADİSİ</b>\n\n<i>“{secilen['metin']}”</i>\n\n📚 {secilen['kaynak']}", parse_mode=ParseMode.HTML)

# =========================
# 4. SİSTEM ÇALIŞTIRMA
# =========================

def main():
    if not TOKEN:
        print("TOKEN Bulunamadı! Mevzu patlak.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    
    print("Bot marşa bastı, Ankara sokaklarında dolanıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
