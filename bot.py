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
# AYARLAR VE DEĞİŞKENLER
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
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

HADISLER = load_json(HADIS_DOSYA)

def get_all_chats():
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
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
# 2. API VE ZAMAN FONKSİYONLARI
# =========================

def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower().strip()

def find_location_id(city):
    """Şehir ID'sini bulur, hata yönetimli."""
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data[0].get("id") if (data and isinstance(data, list)) else None
    except Exception as e:
        print(f"Konum Hatası ({city}): {e}")
        return None

def get_prayertimes(location_id):
    """Vakitleri çeker, NoneType hatasını önler."""
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data and isinstance(data, list):
            return data[0]
        return None
    except Exception as e:
        print(f"Vakit API Hatası: {e}")
        return None

def time_until(vakit_str, next_day_if_passed=False):
    if not vakit_str: return 0, 0, "--:--"
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    
    if next_day_if_passed and now >= vakit_time:
        vakit_time += timedelta(days=1)
        
    delta = vakit_time - now
    total_seconds = max(0, int(delta.total_seconds()))
    return total_seconds // 3600, (total_seconds % 3600) // 60, vakit_time.strftime("%H:%M")

# =========================
# 3. MESAJ ŞABLONLARI (PROFESYONEL)
# =========================

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <b>Şehir girmediniz.</b>\nÖrn: <code>/iftar Istanbul</code>", parse_mode=ParseMode.HTML)
        return
    
    city = " ".join(context.args)
    loc_id = find_location_id(normalize(city))
    
    if not loc_id:
        await update.message.reply_text("❌ <b>Şehir bulunamadı!</b>\nLütfen yazımı kontrol edin (Örn: <i>Ankara, Izmir</i>).", parse_mode=ParseMode.HTML)
        return
        
    times = get_prayertimes(loc_id)
    if not times or not times.get("maghrib"):
        await update.message.reply_text("📡 <b>API Sunucusu Yanıt Vermiyor.</b>\nLütfen bir kaç dakika sonra tekrar deneyin.", parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(times.get("maghrib"), True)
    mesaj = (
        f"🕌 <b>İFTAR VAKTİ | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"🕓 <b>Akşam Ezanı:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"🤲 <b>İftar Duası:</b>\n"
        f"<i>'Allah'ım senin rızan için oruç tuttum, senin rızkınla orucumu açıyorum.'</i>\n\n"
        f"✨ <b>Hayırlı İftarlar dileriz.</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <b>Şehir girmediniz.</b>", parse_mode=ParseMode.HTML)
        return
        
    city = " ".join(context.args)
    loc_id = find_location_id(normalize(city))
    
    if not loc_id:
        await update.message.reply_text("❌ <b>Şehir bulunamadı!</b>", parse_mode=ParseMode.HTML)
        return
        
    times = get_prayertimes(loc_id)
    if not times or not times.get("fajr"):
        await update.message.reply_text("📡 <b>Vakit bilgisi şu an alınamıyor.</b>", parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(times.get("fajr"), True)
    mesaj = (
        f"🌌 <b>SAHUR (İMSAK) | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"📢 <b>İmsak Vakti:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"💡 <b>Niyet:</b>\n"
        f"<i>'Niyet ettim Allah rızası için bugünkü Ramazan orucunu tutmaya.'</i>\n\n"
        f"🤲 <b>Bereketli Sahurlar.</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    # 2026 Ramazan Başlangıcı: 19 Şubat
    start_date = datetime(2026, 2, 19).date()
    end_date = datetime(2026, 3, 19).date()
    
    if now < start_date:
        kalan = (start_date - now).days
        mesaj = f"⏳ <b>RAMAZAN'A KAVUŞMAYA</b>\n\n🌙 On bir ayın sultanına son <b>{kalan} gün</b> kaldı!"
    elif now > end_date:
        mesaj = "👋 <b>Elveda Ya Şehr-i Ramazan...</b>\n\nRabbim tekrarına kavuştursun."
    else:
        # Hata Çözümü: 19 Şubatta (now-start).days 0 olduğu için +1 ekliyoruz.
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN-I ŞERİF</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
            f"🗓 Bugün Ramazan'ın <b>{gun}. günü</b>.\n\n"
            f"<i>Rabbim oruçlarınızı ve dualarınızı makbul eylesin.</i>"
        )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# =========================
# 4. DİĞER FONKSİYONLAR
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    mesaj = (
        "<b>🌙 Hoş Geldiniz!</b>\n\n"
        "Ramazan rehberiniz aktif. Aşağıdaki komutları kullanabilirsiniz:\n\n"
        "🍽 /iftar <code>şehir</code>\n"
        "🥣 /sahur <code>şehir</code>\n"
        "📜 /hadis\n"
        "📅 /ramazan"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("📜 <i>Sabır en büyük ibadettir.</i>")
        return
    secilen = random.choice(HADISLER)
    await update.message.reply_text(f"📜 <b>GÜNÜN HADİSİ</b>\n\n<i>“{secilen['metin']}”</i>\n\n📚 {secilen['kaynak']}", parse_mode=ParseMode.HTML)

async def otomatik_hadis_paylas(context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER: return
    chats = get_all_chats()
    secilen = random.choice(HADISLER)
    mesaj = f"✨ <b>GÜNÜN HATIRLATMASI</b>\n┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n<i>“{secilen['metin']}”</i>\n\n📚 <b>Kaynak:</b> {secilen['kaynak']}"
    for chat in chats:
        if chat.get("type") in ["group", "supergroup"]:
            try:
                await context.bot.send_message(chat["chat_id"], mesaj, parse_mode=ParseMode.HTML)
                await asyncio.sleep(0.05)
            except: continue

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS: return
    if not update.message.reply_to_message: return
    reply = update.message.reply_to_message
    chats = get_all_chats()
    basarili = 0
    for chat in chats:
        try:
            await context.bot.copy_message(chat_id=chat["chat_id"], from_chat_id=reply.chat_id, message_id=reply.message_id)
            basarili += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ {basarili} sohbete iletildi.")

async def kaydet_mesaj_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message: kaydet_chat_id(update.message.chat_id, update.message.chat.type)

def main():
    if not TOKEN:
        print("HATA: TOKEN bulunamadı!")
        return
        
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Job Queue (Hadis Döngüsü)
    app.job_queue.run_repeating(otomatik_hadis_paylas, interval=21600, first=10)

    # Komutlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kaydet_mesaj_chat))
    
    print("Bot 2026 Ramazan modunda aktif!")
    app.run_polling()

if __name__ == "__main__":
    main()
