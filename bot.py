import os, json, httpx, asyncio, pytz, random, logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# =========================
# ⚙️ AYARLAR VE HAFIZA
# =========================
logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("TOKEN") 
ADMIN_IDS = [6563936773, 6030484208]
CHATS_FILE = "chats.json"
CITY_CACHE = {} 

HADISLER = [
    "Oruç tutunuz ki sıhhat bulasınız.",
    "Kim bir oruçluya iftar ettirirse, sevabı kadar sevap yazılır.",
    "Ramazan ayı girdiği zaman cennet kapıları açılır.",
    "Oruçlu için iki sevinç vardır: İftar vakti ve Rabbine kavuştuğu an.",
    "Ramazan'ın başı rahmet, ortası mağfiret, sonu cehennemden kurtuluştur.",
    "Allah'ım! Sen affedicisin, affetmeyi seversin, beni de affet."
]

# =========================
# 💾 KULLANICI YÖNETİMİ
# =========================
def load_chats():
    if os.path.exists(CHATS_FILE):
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

async def save_chat_async(chat_id):
    try:
        chats = load_chats()
        if not any(c['chat_id'] == chat_id for c in chats):
            chats.append({"chat_id": chat_id})
            with open(CHATS_FILE, "w", encoding="utf-8") as f: json.dump(chats, f)
    except: pass

# =========================
# 🚀 ANTI-BLOKAJ API MOTORU (ÖZEL KİMLİK)
# =========================
async def get_times_pro(city_input):
    tr_map = str.maketrans("çğıöşüİĞÜŞÖÇ", "cgiosuiguuoc")
    city_clean = city_input.translate(tr_map).lower().strip().replace(" ", "-")
    
    # Şehir hafızadaysa saniyesinde ver
    if city_clean in CITY_CACHE:
        exp, data = CITY_CACHE[city_clean]
        if datetime.now() < exp: return data

    # 🛡️ BURASI ÇOK ÖNEMLİ: Güvenlik duvarını aşmak için tarayıcı kimliği
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    # timeout süresi 20 saniye yapıldı, yönlendirmelere izin verildi
    async with httpx.AsyncClient(headers=headers, timeout=20.0, follow_redirects=True) as client:
        
        # 1. Deneme: Şehir İsmiyle (Diyanet Metodu)
        try:
            url1 = f"https://api.aladhan.com/v1/timingsByCity?city={city_clean}&country=Turkey&method=13"
            res1 = await client.get(url1)
            if res1.status_code == 200:
                d = res1.json()["data"]["timings"]
                res_obj = {"v": d, "tz": "Europe/Istanbul", "yer": city_input.upper()}
                CITY_CACHE[city_clean] = (datetime.now() + timedelta(hours=6), res_obj)
                return res_obj
        except Exception as e: logging.error(f"API 1 Hata: {e}")

        # 2. Deneme: Adres Bazlı (İlkinde blok yerse buradan sızar)
        try:
            url2 = f"https://api.aladhan.com/v1/timingsByAddress?address={city_clean},Turkey&method=13"
            res2 = await client.get(url2)
            if res2.status_code == 200:
                d = res2.json()["data"]["timings"]
                res_obj = {"v": d, "tz": "Europe/Istanbul", "yer": city_input.upper()}
                CITY_CACHE[city_clean] = (datetime.now() + timedelta(hours=6), res_obj)
                return res_obj
        except Exception as e: logging.error(f"API 2 Hata: {e}")

        # 3. Deneme: Tamamen Farklı Bir API (Yedek)
        try:
            url3 = f"https://api.pray.zone/v2/times/today.json?city={city_clean}"
            res3 = await client.get(url3)
            if res3.status_code == 200:
                d = res3.json()["results"]["datetime"][0]["times"]
                res_obj = {"v": {"Fajr": d["Fajr"], "Maghrib": d["Maghrib"]}, "tz": "Europe/Istanbul", "yer": city_input.upper()}
                CITY_CACHE[city_clean] = (datetime.now() + timedelta(hours=6), res_obj)
                return res_obj
        except Exception as e: logging.error(f"API 3 Hata: {e}")

    return None

# =========================
# 🎭 ANA İŞLEMCİ (DİNAMİK MESAJLI)
# =========================
async def vakit_hesapla(update: Update, context: ContextTypes.DEFAULT_TYPE, mode):
    if not update.message: return
    city = " ".join(context.args) if context.args else None
    
    if not city:
        await update.message.reply_text("📍 Lütfen şehir yazın.\nÖrn: <code>/iftar Ankara</code>", parse_mode=ParseMode.HTML)
        return

    # Kullanıcıya beklemesi için anında dönüt veriyoruz
    bekleme_mesaji = await update.message.reply_text("⏳ <i>Sunucuya bağlanılıyor, lütfen bekleyin...</i>", parse_mode=ParseMode.HTML)

    data = await get_times_pro(city)
    if not data:
        await bekleme_mesaji.edit_text("⚠️ <b>Bağlantı Kurulamadı!</b>\nŞehir adını doğru yazdığınızdan emin olun. (API sunucuları geçici olarak yanıt vermiyor olabilir)", parse_mode=ParseMode.HTML)
        return

    try:
        tz = pytz.timezone(data["tz"])
        now = datetime.now(tz)
        v_saat = data["v"][mode]
        
        target = now.replace(hour=int(v_saat.split(":")[0]), minute=int(v_saat.split(":")[1]), second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        diff = int((target - now).total_seconds())
        
        p = min(1, max(0, 1 - (diff / 57600)))
        bar = "🔵" * int(10 * p) + "⚪" * (10 - int(10 * p))
        label = "İFTARA" if mode == "Maghrib" else "SAHURA"

        mesaj = (
            f"✨ <b>{label} NE KADAR KALDI?</b> ✨\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"📍 <b>Bölge:</b> {data['yer']}\n"
            f"⏰ <b>Vakit:</b> {v_saat}\n"
            f"⏳ <b>Kalan:</b> {diff//3600} saat {(diff%3600)//60} dk\n\n"
            f"<b>Doluluk:</b> {bar} %{int(p*100)}\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n"
            f"✨ <i>{random.choice(HADISLER)}</i>"
        )
        # Bekleme mesajını asıl veriyle değiştiriyoruz
        await bekleme_mesaji.edit_text(mesaj, parse_mode=ParseMode.HTML)
    except:
        await bekleme_mesaji.edit_text("❌ Hesaplama hatası oluştu.")

# =========================
# 🛠️ KOMUTLAR VE PANEL
# =========================
async def start(u, c):
    await save_chat_async(u.effective_chat.id)
    kb = [[InlineKeyboardButton("🍽 İftar Vakti", callback_data='i'), InlineKeyboardButton("🥣 Sahur Vakti", callback_data='s')],
          [InlineKeyboardButton("📜 Günün Hadisi", callback_data='h')]]
    await u.message.reply_text("✨ <b>RAMAZAN VAKİT BOT v32</b> ✨\nHoş geldiniz. Komutunuzu seçin veya şehir girin.", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def duyuru_yolla(u, c):
    if u.effective_user.id not in ADMIN_IDS: return
    msg = " ".join(c.args)
    if not msg: return
    for user in load_chats():
        try: await c.bot.send_message(user["chat_id"], f"📢 <b>DUYURU</b>\n\n{msg}", parse_mode=ParseMode.HTML); await asyncio.sleep(0.05)
        except: pass
    await u.message.reply_text("✅ Duyuru gönderildi.")

async def cb_handler(u, c):
    q = u.callback_query
    await q.answer()
    if q.data == 'h': await q.message.reply_text(f"📜 <i>{random.choice(HADISLER)}</i>", parse_mode=ParseMode.HTML)
    else: await q.message.reply_text("📍 Sorgu için: <code>/iftar Şehir</code> yazın.", parse_mode=ParseMode.HTML)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", lambda u,c: vakit_hesapla(u,c,"Maghrib")))
    app.add_handler(CommandHandler("sahur", lambda u,c: vakit_hesapla(u,c,"Fajr")))
    app.add_handler(CommandHandler("duyuru", duyuru_yolla))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, lambda u,c: save_chat_async(u.effective_chat.id)))
    print("🚀 v32 ANTI-BLOKAJ MODU AKTİF!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
