import os
import json
import requests
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
# 🚀 ÇİFT MOTORLU ŞEHİR ÇÖZÜCÜ (v21)
# =========================
def get_prayertimes(city_input):
    if not city_input: return None
    
    # 1. TEMİZLİK: API'nin anlayacağı basit İngilizce karakterler
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip()
    
    # 2. DENEME: Farklı API kombinasyonları
    # Bazı API'ler 'istanbul' bazıları 'istanbul-turkey' ister.
    test_urls = [
        f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13",
        f"https://api.aladhan.com/v1/timingsByCity?city={city_clean.replace(' ', '-')}&country=Turkey&method=13",
        f"http://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=TR&method=13"
    ]
    
    for url in test_urls:
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("data") and "timings" in data["data"]:
                    return {
                        "vakitler": data["data"]["timings"], 
                        "timezone": data["data"]["meta"]["timezone"], 
                        "yer": city_input.upper()
                    }
        except:
            continue
            
    return None

# =========================
# 💾 VERİ TABANI SİSTEMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "date": datetime.now().strftime("%d.%m.%Y")})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🎭 ANA MOTOR
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        return await update.message.reply_text("📍 Lütfen şehir yazın. Örn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)

    # API Sorgusu Başlat
    data = get_prayertimes(city)
    
    if not data:
        return await update.message.reply_text(
            f"❌ <b>'{city}'</b> şehri maalesef bulunamadı.\n\n"
            "💡 <b>Çözüm:</b> Şehir ismini <code>Sanliurfa, Istanbul, Izmir</code> gibi İngilizce karakterlerle yazmayı deneyin.",
            parse_mode=ParseMode.HTML
        )

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0)
        
        if now >= target: target += timedelta(days=1)
        diff = target - now
        sec = int(diff.total_seconds())
        
        # Premium Bar
        progress = min(1, max(0, 1 - (sec / 57600)))
        bar = "🌕" * int(10 * progress) + "🌑" * (10 - int(10 * progress))

        header = "🌙 İFTAR" if mode == "Maghrib" else "🥣 SAHUR"
        mesaj = (
            f"✨ <b>{header} | {data['yer']}</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(progress*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"🤲 <i>Hayırlı Ramazanlar.</i>"
        )
        await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)
    except:
        await update.message.reply_text("⚠️ Bir hata oluştu, lütfen az sonra tekrar deneyin.")

# =========================
# 🛠️ ADMIN VE DİĞERLERİ
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await save_chat(update.effective_chat.id)
    await update.message.reply_text("🌙 <b>Ramazan Botu v21 Aktif!</b>\nŞehir yazarak sorgu yapabilirsiniz.", parse_mode=ParseMode.HTML)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(f"📊 Toplam Kullanıcı: {len(load_chats())}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat(u.effective_chat.id)))
    app.run_polling()

if __name__ == "__main__":
    main()
