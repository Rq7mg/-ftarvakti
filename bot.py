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

# Ortam değişkeninden Token'ı al
TOKEN = os.environ.get("TOKEN")

# Admin ID'leri
ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"
HADIS_DOSYA = "hadisler.json"

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
    except Exception as e:
        print("Kayıt hatası:", e)

# =========================
# 2. YARDIMCI FONKSİYONLAR
# =========================

def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower()

def find_location_id(city):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0].get("id") if data else None
    except:
        return None

def get_prayertimes(location_id):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0] if data and len(data) > 0 else None
    except:
        return None

tz = pytz.timezone("Europe/Istanbul")

def time_until(vakit_str, next_day_if_passed=False):
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    
    if next_day_if_passed and now >= vakit_time:
        vakit_time += timedelta(days=1)
        
    delta = vakit_time - now
    total_seconds = int(delta.total_seconds())
    
    # Eğer vakit geçtiyse negatif dönmemesi için
    if total_seconds < 0: total_seconds = 0
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes, vakit_time.strftime("%H:%M")

# =========================
# 3. OTOMATİK GÖREVLER
# =========================

async def otomatik_hadis_paylas(context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER: return
    chats = get_all_chats()
    secilen = random.choice(HADISLER)
    
    mesaj = (
        "✨ <b>GÜNÜN MANEVİ HATIRLATMASI</b>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"<i>“{secilen['metin']}”</i>\n\n"
        f"📚 <b>Kaynak:</b> {secilen['kaynak']}\n\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "🕊 <i>Hayırlı ve bereketli vakitler dileriz.</i>"
    )

    for chat in chats:
        if chat.get("type") in ["group", "supergroup"]:
            try:
                await context.bot.send_message(chat["chat_id"], mesaj, parse_mode=ParseMode.HTML)
                await asyncio.sleep(0.05) 
            except: continue

# =========================
# 4. BOT KOMUTLARI
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    
    mesaj = (
        "<b>🌙 Ramazan-ı Şerif Rehberine Hoş Geldiniz!</b>\n\n"
        "Mübarek Ramazan ayında iftar, sahur ve manevi paylaşımlarla yanınızdayız.\n\n"
        "📜 <b>Hizmetlerimiz:</b>\n"
        "◽️ <b>/iftar &lt;şehir&gt;</b> - İftar vakti ve kalan süre.\n"
        "◽️ <b>/sahur &lt;şehir&gt;</b> - İmsak vakti ve kalan süre.\n"
        "◽️ <b>/hadis</b> - Kalpleri ferahlatan hadis-i şerifler.\n"
        "◽️ <b>/ramazan</b> - Gün sayacı ve takvim.\n\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        "<i>Rabbim tuttuğunuz oruçları kabul eylesin.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ <b>Hata:</b> Lütfen bir şehir adı yazın.\nÖrnek: <code>/iftar Bursa</code>", parse_mode=ParseMode.HTML)
        return
    
    city_input = " ".join(context.args)
    loc_id = find_location_id(normalize(city_input))
    
    if not loc_id:
        await update.message.reply_text("❌ <b>Şehir bulunamadı.</b>\nLütfen yazımı kontrol edin.", parse_mode=ParseMode.HTML)
        return
        
    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("📡 <b>API Hatası:</b> Vakit verileri şu an alınamıyor.", parse_mode=ParseMode.HTML)
        return

    maghrib = times.get("maghrib")
    h, m, saat = time_until(maghrib, True)
    
    mesaj = (
        f"🕌 <b>İFTAR VAKTİ | {city_input.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"🕓 <b>Akşam Ezanı:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"🤲 <b>İftar Duası:</b>\n"
        f"<i>'Allahumme leke sumtu ve bike amentu ve aleyke tevekkeltu ve ala rizkike eftartu.'</i>\n\n"
        f"✨ <b>Hayırlı İftarlar...</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ <b>Hata:</b> Lütfen bir şehir adı yazın.\nÖrnek: <code>/sahur Konya</code>", parse_mode=ParseMode.HTML)
        return
        
    city_input = " ".join(context.args)
    loc_id = find_location_id(normalize(city_input))
    
    if not loc_id:
        await update.message.reply_text("❌ <b>Şehir bulunamadı.</b>", parse_mode=ParseMode.HTML)
        return
        
    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("📡 <b>API Hatası:</b> Veriler şu an yüklenemedi.", parse_mode=ParseMode.HTML)
        return

    fajr = times.get("fajr")
    h, m, saat = time_until(fajr, True)
    
    mesaj = (
        f"🌌 <b>SAHUR VAKTİ (İMSAK) | {city_input.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"📢 <b>İmsak Saati:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"💡 <b>Günün Niyeti:</b>\n"
        f"<i>'Niyet ettim Allah rızası için bugünkü Ramazan orucunu tutmaya.'</i>\n\n"
        f"🤲 <b>Bereketli Sahurlar.</b>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    start_date = datetime(2026, 2, 18).date() # 2026 Ramazan başlangıcı 18 Şubattır (Tahmini)
    end_date = datetime(2026, 3, 19).date()
    
    if now < start_date:
        kalan = (start_date - now).days
        mesaj = f"⌛ <b>SULTANIN GELİŞİNE</b>\n\n🌙 Ramazan-ı Şerif'e kavuşmaya <b>{kalan} gün</b> kaldı."
    elif now > end_date:
        mesaj = "👋 <b>Elveda Ya Şehr-i Ramazan...</b>\n\nŞu an Ramazan ayında değiliz. Rabbim tekrarına kavuştursun."
    else:
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN-I ŞERİF</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
            f"🗓 Bugün Ramazan'ın <b>{gun}. günü</b>.\n\n"
            f"<i>Rabbim oruçlarınızı ve dualarınızı makbul eylesin.</i>"
        )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("⚠️ <i>Yüklü hadis bulunamadı.</i>", parse_mode=ParseMode.HTML)
        return

    secilen = random.choice(HADISLER)
    mesaj = (
        "📜 <b>GÜNÜN HADİS-İ ŞERİFİ</b>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"<i>“{secilen['metin']}”</i>\n\n"
        f"📚 <b>Kaynak:</b> {secilen['kaynak']}"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS: return
    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Bir mesajı yanıtlayarak duyuru yapın.")
        return

    reply = update.message.reply_to_message
    chats = get_all_chats()
    basarili = 0
    header = "📢 <b>BİLGİLENDİRME</b>\n┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"

    for chat in chats:
        try:
            if reply.text:
                await context.bot.send_message(chat["chat_id"], f"{header}{reply.text}", parse_mode=ParseMode.HTML)
            elif reply.photo:
                await context.bot.send_photo(chat["chat_id"], photo=reply.photo[-1].file_id, 
                                            caption=f"{header}{reply.caption or ''}", parse_mode=ParseMode.HTML)
            basarili += 1
            await asyncio.sleep(0.05)
        except: pass

    await update.message.reply_text(f"✅ {basarili} kişiye ulaşıldı.")

async def kaydet_mesaj_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        kaydet_chat_id(update.message.chat_id, update.message.chat.type)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Zamanlayıcı
    job_queue = app.job_queue
    job_queue.run_repeating(otomatik_hadis_paylas, interval=21600, first=10)

    # Handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kaydet_mesaj_chat))
    
    print("Bot aktif ve güvenli modda çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
