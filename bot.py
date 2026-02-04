import os
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random
from pymongo import MongoClient

TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")  # MongoDB URI

# --------------------------
# MongoDB Bağlantısı
# --------------------------
client = MongoClient(MONGO_URI)
db = client["iftarbot"]          
chats_collection = db["chats"]   

# --------------------------
# ADMIN user id
# --------------------------
ADMIN_IDS = [6563936773, 6030484208]

# --------------------------
# Diyanet API fonksiyonları
# --------------------------
def find_location_id(city):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0].get("id")
    except Exception as e:
        print("find_location_id HATA:", e)
        return None

def get_prayertimes(location_id):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0]
    except Exception as e:
        print("get_prayertimes HATA:", e)
        return None

# --------------------------
# Zaman hesapları
# --------------------------
tz = pytz.timezone("Europe/Istanbul")

def time_until(vakit_str, next_day_if_passed=False):
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if next_day_if_passed and now >= vakit_time:
        vakit_time += timedelta(days=1)
    delta = vakit_time - now
    total_minutes = int(delta.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return hours, minutes, vakit_time.strftime("%H:%M")

# --------------------------
# /start
# --------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type  # 'private', 'group', 'supergroup', 'channel'
    
    # Daha önce kaydedilmemişse ekle
    if chats_collection.find_one({"chat_id": chat_id}) is None:
        chats_collection.insert_one({
            "chat_id": chat_id,
            "type": chat_type
        })

    await update.message.reply_text(
        "🕌 Diyanet İftar & Sahur Vakti Botu hazır!\n\n"
        "Komutlar:\n"
        "/iftar <şehir>\n"
        "/sahur <şehir>\n"
        "/duyuru <mesaj> → Bot yöneticisi için\n"
        "/hadis → Rastgele Türkçe hadis\n"
        "/ramazan → Ramazan günü veya kaç gün kaldı"
    )

# --------------------------
# /iftar
# --------------------------
async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /iftar <şehir>")
        return

    city = context.args[0]
    loc_id = find_location_id(city)
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return

    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("Namaz vakitleri alınamadı.")
        return

    maghrib = times.get("maghrib") or times.get("Maghrib")
    hours, minutes, saat = time_until(maghrib, next_day_if_passed=True)

    now = datetime.now(tz)
    vakit_time = now.replace(hour=int(maghrib.split(":")[0]), minute=int(maghrib.split(":")[1]), second=0)
    if now < vakit_time:
        await update.message.reply_text(
            f"📍 {city.title()}\n🍽️ İftara {hours} saat {minutes} dakika kaldı ({saat})"
        )
    else:
        await update.message.reply_text(
            f"📍 {city.title()}\n🌙 İftar vakti geçti, bir sonraki vakit: {saat}"
        )

# --------------------------
# /sahur
# --------------------------
async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /sahur <şehir>")
        return

    city = context.args[0]
    loc_id = find_location_id(city)
    if not loc_id:
        await update.message.reply_text("Şehir bulunamadı.")
        return

    times = get_prayertimes(loc_id)
    if not times:
        await update.message.reply_text("Namaz vakitleri alınamadı.")
        return

    fajr = times.get("fajr") or times.get("Fajr")
    hours, minutes, saat = time_until(fajr, next_day_if_passed=True)

    await update.message.reply_text(
        f"📍 {city.title()}\n🌙 Sahura {hours} saat {minutes} dakika kaldı ({saat})"
    )

# --------------------------
# /duyuru
# --------------------------
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Bu komutu sadece bot yöneticisi kullanabilir.")
        return

    if not context.args:
        await update.message.reply_text("Kullanım: /duyuru <mesaj>")
        return

    mesaj = " ".join(context.args)
    chats = [doc["chat_id"] for doc in chats_collection.find()]
    count = 0

    for chat_id in chats:
        try:
            await context.bot.send_message(chat_id, f"📢 Duyuru:\n\n{mesaj}")
            count += 1
        except Exception as e:
            print("Duyuru gönderilemedi:", chat_id, e)

    await update.message.reply_text(f"Duyuru gönderildi! ({count} chat)")

# --------------------------
# /ramazan
# --------------------------
RAMAZAN_START = datetime(2026, 2, 19)
RAMAZAN_END = datetime(2026, 3, 19)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    start = RAMAZAN_START.date()
    end = RAMAZAN_END.date()

    if now < start:
        kalan = (start - now).days
        await update.message.reply_text(f"🌙 Ramazan’a {kalan} gün kaldı.")
        return

    if now > end:
        await update.message.reply_text("🌙 Bu yılki Ramazan sona erdi. Allah kabul etsin 🤲")
        return

    gun = (now - start).days + 1
    await update.message.reply_text(f"🌙 Bugün Ramazan’ın {gun}. günü.")

# --------------------------
# /hadis
# --------------------------
HADISLER = [
    "Mümin, insanların elinden ve dilinden emin olan kimsedir.",
    "Kolaylaştırın, zorlaştırmayın.",
    "Komşusu aç iken tok yatan bizden değildir.",
    "Sözünüz güzel olsun, kalbiniz güzel olsun.",
    "İyilik edenin iyiliği karşılıksız kalmaz.",
    "Gülümseyen yüz sadakadır.",
    "Sabır imanın yarısıdır.",
    "İyilik eden, ölmez, kalır.",
    "Komşuya eziyet etmeyen cennete girer.",
    "İlim öğrenmek ibadettir.",
    "Sadaka fakiri zengin eder.",
    "Helal kazanç berekettir.",
    "Doğru söz cennete götürür.",
]

USED_HADIS = []

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USED_HADIS
    try:
        if len(USED_HADIS) == len(HADISLER):
            USED_HADIS = []

        kalan = list(set(HADISLER) - set(USED_HADIS))
        secilen = random.choice(kalan)
        USED_HADIS.append(secilen)

        await update.message.reply_text(f"📜 Hadis\n\n“{secilen}”")
    except Exception as e:
        print("Hadis Hatası:", e)
        await update.message.reply_text("⚠️ Hadis alınırken bir hata oluştu.")

# --------------------------
# /stats (admin sadece)
# --------------------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Bu komutu sadece bot yöneticisi kullanabilir.")
        return

    total_chats = chats_collection.count_documents({})
    private_chats = chats_collection.count_documents({"type": "private"})
    group_chats = chats_collection.count_documents({"type": {"$in": ["group", "supergroup"]}})

    await update.message.reply_text(
        f"📊 Bot İstatistikleri:\n\n"
        f"Toplam kayıtlı chat: {total_chats}\n"
        f"Özel mesaj (kişiler): {private_chats}\n"
        f"Gruplar: {group_chats}"
    )

# --------------------------
# Main
# --------------------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(CommandHandler("stats", stats))

    print("Bot başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
