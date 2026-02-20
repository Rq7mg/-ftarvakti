import os
import json
import requests
import random
import asyncio
import pytz
from datetime import datetime, timedelta
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# AYARLAR (Config)
# =========================
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"
HADIS_DOSYA = "hadisler.json"

# =========================
# 1. VERİ YÖNETİMİ
# =========================

def load_json(dosya):
    try:
        if os.path.exists(dosya):
            with open(dosya, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Dosya okuma hatası: {e}")
    return []

HADISLER = load_json(HADIS_DOSYA) or [
    {"metin": "Oruç tutunuz ki sıhhat bulasınız.", "kaynak": "Taberânî"}
]

def get_all_chats():
    return load_json(CHAT_FILE)

def kaydet_chat_id(chat_id, chat_type):
    try:
        chats = get_all_chats()
        if not any(c["chat_id"] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": str(chat_type)})
            with open(CHAT_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f, indent=4)
    except Exception as e:
        print(f"⚠️ Kayıt hatası: {e}")

# =========================
# 2. YARDIMCI FONKSİYONLAR
# =========================

def get_prayertimes(city):
    try:
        headers = {'User-Agent': 'KiyiciZeminBot/3.0'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        geo_req = requests.get(geo_url, headers=headers, timeout=10)
        geo_data = geo_req.json()
        if not geo_data: return None, None, None
        lat, lon = geo_data[0]['lat'], geo_data[0]['lon']
        gercek_yer = geo_data[0]['display_name'].split(",")[0]
        aladhan_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        r = requests.get(aladhan_url, timeout=10)
        data = r.json()
        if r.status_code == 200:
            return data["data"]["timings"], data["data"]["meta"]["timezone"], gercek_yer
    except: pass
    return None, None, None

def time_until(vakit_str, tz_name):
    target_tz = pytz.timezone(tz_name)
    now_local = datetime.now(target_tz)
    h, m = map(int, vakit_str.split(" ")[0].split(":"))
    vakit_time = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    if now_local >= vakit_time: vakit_time += timedelta(days=1)
    delta = vakit_time - now_local
    ts = int(delta.total_seconds())
    return ts // 3600, (ts % 3600) // 60, vakit_str.split(" ")[0]

# =========================
# 3. YENİ KOMUTLAR (Stats & Duyuru)
# =========================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    
    chats = get_all_chats()
    user_count = sum(1 for c in chats if "private" in c.get("type", ""))
    group_count = sum(1 for c in chats if "group" in c.get("type", "").lower() or "supergroup" in c.get("type", "").lower())
    
    mesaj = (
        "<b>📊 BOT İSTATİSTİKLERİ</b>\n"
        "┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
        f"👤 <b>Kullanıcı Sayısı:</b> {user_count}\n"
        f"👥 <b>Grup Sayısı:</b> {group_count}\n"
        f"📈 <b>Toplam Erişim:</b> {len(chats)}"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    
    # Duyurulacak metni belirle (Yanıtlanan mesaj mı yoksa komut sonrası yazılan mı?)
    if update.message.reply_to_message:
        text_to_send = update.message.reply_to_message.text
    elif context.args:
        text_to_send = " ".join(context.args)
    else:
        await update.message.reply_text("❗ <b>Duyuru metni yazmadın ya da bir mesajı yanıtlamadın gardaş!</b>")
        return

    chats = get_all_chats()
    basarili, hatali = 0, 0
    
    bilgi_mesaji = await update.message.reply_text(f"🚀 <b>Duyuru {len(chats)} yere postalanıyor...</b>", parse_mode=ParseMode.HTML)
    
    for chat in chats:
        try:
            await context.bot.send_message(chat_id=chat["chat_id"], text=text_to_send, parse_mode=ParseMode.HTML)
            basarili += 1
            await asyncio.sleep(0.05) # Telegram flood engeli yememek için ufak es
        except:
            hatali += 1
            
    await bilgi_mesaji.edit_text(
        f"✅ <b>Duyuru Tamamlandı!</b>\n\n"
        f"📢 Ulaşan: {basarili}\n"
        f"❌ Hatalı: {hatali} (Botu engellemişler)",
        parse_mode=ParseMode.HTML
    )

# =========================
# 4. DİĞER KOMUTLAR
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    await update.message.reply_text("<b>🌙 Hoş Geldin Gardaş!</b>\nŞehir yaz vakti kap!\n\n/iftar ankara\n/sahur istanbul\n/hadis\n/ramazan", parse_mode=ParseMode.HTML)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Şehir yaz la bebe!")
    city = " ".join(context.args)
    timings, tz, yer = get_prayertimes(city)
    if not timings: return await update.message.reply_text("Böyle yer mi var?")
    h, m, s = time_until(timings["Maghrib"], tz)
    await update.message.reply_text(f"🕌 <b>{yer} İFTAR</b>\n\nEzan: {s}\nKalan: {h} saat {m} dk", parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Şehir yaz la bebe!")
    city = " ".join(context.args)
    timings, tz, yer = get_prayertimes(city)
    if not timings: return await update.message.reply_text("Böyle yer mi var?")
    h, m, s = time_until(timings["Fajr"], tz)
    await update.message.reply_text(f"🌌 <b>{yer} SAHUR</b>\n\nİmsak: {s}\nKalan: {h} saat {m} dk", parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 20.02.2026 tarihi bugün (Sistem tarihine göre)
    now = datetime.now(pytz.timezone("Europe/Istanbul")).date()
    start_date = datetime(2026, 2, 19).date()
    end_date = datetime(2026, 3, 19).date()
    if now < start_date:
        await update.message.reply_text(f"🌙 Ramazan'a {(start_date - now).days} gün kaldı.")
    elif now > end_date:
        await update.message.reply_text("👋 Elveda Ramazan...")
    else:
        await update.message.reply_text(f"🌙 Ramazan'ın {(now - start_date).days + 1}. günündeyiz.")

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sec = random.choice(HADISLER)
    await update.message.reply_text(f"📜 <b>GÜNÜN HADİSİ</b>\n\n<i>“{sec['metin']}”</i>\n\n📚 {sec['kaynak']}", parse_mode=ParseMode.HTML)

def main():
    if not TOKEN: return print("TOKEN YOK!")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("duyuru", duyuru))
    print("🚀 Bot marşa bastı, Ankara bebesi yollarda...")
    app.run_polling()

if __name__ == "__main__":
    main()

