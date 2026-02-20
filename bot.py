import os
import json
import httpx
import asyncio
import pytz
import random
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

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, kendisine onun sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır, cehennem kapıları kapanır.",
    "Oruçlu için iki sevinç vardır: Biri iftar ettiği vakit, diğeri Rabbine kavuştuğu vakit.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu ise cehennemden kurtuluştur."
]

# =========================
# 🚀 HIZLI ŞEHİR ÇÖZÜCÜ
# =========================
async def get_prayertimes(city_input):
    if not city_input: return None
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res = await client.get(url, timeout=7)
            if res.status_code == 200:
                data = res.json()
                if data.get("data"):
                    return {
                        "vakitler": data["data"]["timings"], 
                        "timezone": data["data"]["meta"]["timezone"], 
                        "yer": city_input.upper()
                    }
        except: return None
    return None

# =========================
# 💾 VERİ YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_chat(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🎭 ANA MOTOR
# =========================
async def engine(update: Update, context: ContextTypes.DEFAULT_TYPE, mode="Maghrib"):
    city = " ".join(context.args) if context.args else None
    if not city:
        await update.message.reply_text("📍 Lütfen şehir yazın.\nÖrn: <code>/iftar İstanbul</code>", parse_mode=ParseMode.HTML)
        return

    data = await get_prayertimes(city)
    if not data:
        await update.message.reply_text(f"❌ <b>'{city}'</b> bulunamadı.\nLütfen yazımı kontrol edin.", parse_mode=ParseMode.HTML)
        return

    try:
        tz = pytz.timezone(data["timezone"])
        now = datetime.now(tz)
        target_str = data["vakitler"][mode]
        h, m = map(int, target_str.split(":"))
        target = now.replace(hour=h, minute=m, second=0)
        
        if now >= target: target += timedelta(days=1)
        diff = target - now
        sec = int(diff.total_seconds())
        
        progress = min(1, max(0, 1 - (sec / 57600)))
        bar = "🌕" * int(10 * progress) + "🌑" * (10 - int(10 * progress))

        header = "🌙 İFTAR" if mode == "Maghrib" else "🥣 SAHUR"
        mesaj = (
            f"⚜️ <b>{header} | {data['yer']}</b> ⚜️\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"⏰ <b>Vakit:</b> <code>{target_str}</code>\n"
            f"⏳ <b>Kalan:</b> <code>{sec//3600}s {(sec%3600)//60}dk</code>\n\n"
            f"<code>{bar}</code>  <b>%{int(progress*100)}</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📜 <i>{random.choice(HADISLER)}</i>"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=mesaj, parse_mode=ParseMode.HTML)
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Bir hata oluştu.")

# =========================
# 📜 ÖZEL KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_chat(update.effective_chat.id)
    keyboard = [
        [InlineKeyboardButton("🌙 İftar", callback_data='btn_i'), InlineKeyboardButton("🥣 Sahur", callback_data='btn_s')],
        [InlineKeyboardButton("📜 Rastgele Hadis", callback_data='btn_h')]
    ]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="⚜️ <b>RAMAZAN ELITE v23</b> ⚜️\n\nHoş geldiniz! Şehir yazarak veya butonları kullanarak vakitleri öğrenebilirsiniz.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📜 <b>Günün Hadisi:</b>\n\n<i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Kullanım: <code>/duyuru mesaj</code>", parse_mode=ParseMode.HTML)
        return
    
    chats = load_chats()
    s, f = 0, 0
    for c in chats:
        try:
            await context.bot.send_message(chat_id=c["chat_id"], text=f"📢 <b>ÖNEMLİ DUYURU</b>\n\n{text}", parse_mode=ParseMode.HTML)
            s += 1
            await asyncio.sleep(0.05) # Telegram limiti için küçük bekleme
        except: f += 1
    await update.message.reply_text(f"✅ Duyuru bitti.\nBaşarılı: {s}\nHatalı: {f}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text(f"📊 <b>Toplam Kullanıcı:</b> <code>{len(load_chats())}</code>", parse_mode=ParseMode.HTML)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == 'btn_i': await q.message.reply_text("🍽 <code>/iftar şehir</code> yazın.")
    elif q.data == 'btn_s': await q.message.reply_text("🥣 <code>/sahur şehir</code> yazın.")
    elif q.data == 'btn_h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u, c: engine(u, c, "Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u, c: engine(u, c, "Fajr")))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: save_chat(u.effective_chat.id)))
    
    print("🚀 v23 YAYINDA! HER ŞEY EKSİKSİZ.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
