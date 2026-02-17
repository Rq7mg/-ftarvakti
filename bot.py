import os
import json
import requests
from datetime import datetime, timedelta
import pytz
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import random

TOKEN = os.environ.get("TOKEN")

ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"

# =========================
# JSON'dan hadis yükleme
# =========================
HADIS_DOSYA = "hadisler.json"

def load_json(dosya):
    try:
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ {dosya} bulunamadı.")
        return []

HADISLER = load_json(HADIS_DOSYA)

# --------------------------
# Mevcut fonksiyonlar (chat kaydetme, normalize vb.)
# --------------------------
def kaydet_chat_id(chat_id, chat_type):
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                chats = json.load(f)
        else:
            chats = []

        if not any(c["chat_id"] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": chat_type})
            with open(CHAT_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f)
    except Exception as e:
        print("chat_id kaydetme hatası:", e)

def get_all_chats():
    try:
        if os.path.exists(CHAT_FILE):
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    except:
        return []

def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower()

def find_location_id(city):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if not data:
            return None
        return data[0].get("id")
    except:
        return None

def get_prayertimes(location_id):
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/prayertimes?location_id={location_id}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0] if data else None
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
    total_minutes = int(delta.total_seconds() / 60)
    return total_minutes // 60, total_minutes % 60, vakit_time.strftime("%H:%M")

# ==========================
# GÜNCELLENMİŞ START KOMUTU
# ==========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    
    mesaj = (
        "<b>🌙 Hoş Geldiniz, Kıymetli Gönül Dostu!</b>\n\n"
        "Ramazan-ı Şerif'in bereketini, huzurunu ve maneviyatını "
        "birlikte yaşamak için buradayız. Bu bot, sizlere vaktin çağrısını "
        "ve günün manevi rızkını ulaştırmak için tasarlanmıştır.\n\n"
        "👇 <b>Kullanabileceğiniz Hizmetler:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🍽 <b>/iftar &lt;şehir&gt;</b> : İftar vaktine kalan süreyi ve iftar duasını gösterir.\n"
        "🥣 <b>/sahur &lt;şehir&gt;</b> : Sahur vaktini ve niyet duasını paylaşır.\n"
        "📅 <b>/ramazan</b> : Ramazan ayının kaçıncı gününde olduğumuzu söyler.\n"
        "📜 <b>/hadis</b> : Kalbinize dokunacak bir Hadis-i Şerif getirir.\n"
        "📢 <b>/duyuru</b> : (Yöneticiler için) Toplu mesaj gönderir.\n\n"
        "<i>🤲 Rabbim ibadetlerinizi kabul, dualarınızı makbul eylesin.</i>"
    )
    
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def kaydet_mesaj_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)

# ==========================
# GÜNCELLENMİŞ İFTAR KOMUTU
# ==========================
async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <i>Lütfen şehir adı giriniz. Örnek:</i> <code>/iftar Istanbul</code>", parse_mode=ParseMode.HTML)
        return
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    if not loc_id:
        await update.message.reply_text("🚫 <b>Şehir bulunamadı.</b> Lütfen yazımı kontrol ediniz.", parse_mode=ParseMode.HTML)
        return
    times = get_prayertimes(loc_id)
    maghrib = times.get("maghrib")
    h, m, saat = time_until(maghrib, True)
    
    mesaj = (
        f"🕌 <b>İFTAR VAKTİNE DOĞRU</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 <b>Konum:</b> {city_input.capitalize()}\n"
        f"🍽 <b>İftar Saati:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"<i>“Allah'ım! Senin rızan için oruç tuttum, sana inandım, sana güvendim ve senin rızkınla orucumu açıyorum.”</i>\n\n"
        f"✨ <i>Sofranız bereketli, dualarınız kabul olsun.</i>"
    )
    
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# ==========================
# GÜNCELLENMİŞ SAHUR KOMUTU
# ==========================
async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <i>Lütfen şehir adı giriniz. Örnek:</i> <code>/sahur Ankara</code>", parse_mode=ParseMode.HTML)
        return
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    if not loc_id:
        await update.message.reply_text("🚫 <b>Şehir bulunamadı.</b> Lütfen yazımı kontrol ediniz.", parse_mode=ParseMode.HTML)
        return
    times = get_prayertimes(loc_id)
    fajr = times.get("fajr")
    h, m, saat = time_until(fajr, True)
    
    mesaj = (
        f"🌌 <b>SAHUR BEREKETİ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📍 <b>Konum:</b> {city_input.capitalize()}\n"
        f"🥣 <b>İmsak (Sahur Bitiş):</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"💡 <b>Günün Niyeti:</b>\n"
        f"<i>“Niyet ettim Allah rızası için yarınki orucu tutmaya...”</i>\n\n"
        f"🤲 <i>Rabbim tutacağınız oruçları şimdiden kabul eylesin.</i>"
    )
    
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# ==========================
# GÜNCELLENMİŞ DUYURU KOMUTU
# ==========================
async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ <b>Hata:</b> Duyuru yapmak için bir mesaja yanıt vermelisiniz.", parse_mode=ParseMode.HTML)
        return

    reply = update.message.reply_to_message
    chats = get_all_chats()
    basarili = 0

    # Duyuru başlığı
    header_text = "📢 <b>RAMAZAN DUYURUSU</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    for chat in chats:
        try:
            if reply.text:
                await context.bot.send_message(chat["chat_id"], f"{header_text}{reply.text}", parse_mode=ParseMode.HTML)

            elif reply.photo:
                await context.bot.send_photo(
                    chat["chat_id"],
                    photo=reply.photo[-1].file_id,
                    caption=f"{header_text}{reply.caption}" if reply.caption else "📢 <b>RAMAZAN DUYURUSU</b>",
                    parse_mode=ParseMode.HTML
                )

            elif reply.video:
                await context.bot.send_video(
                    chat["chat_id"],
                    video=reply.video.file_id,
                    caption=f"{header_text}{reply.caption}" if reply.caption else "📢 <b>RAMAZAN DUYURUSU</b>",
                    parse_mode=ParseMode.HTML
                )

            basarili += 1
        except:
            pass

    await update.message.reply_text(f"✅ <b>Duyuru Başarıyla Gönderildi.</b>\n📨 Ulaşılan kişi/grup sayısı: <b>{basarili}</b>", parse_mode=ParseMode.HTML)

# ==========================
# GÜNCELLENMİŞ RAMAZAN SAYACI
# ==========================
async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
    # Tarihler kullanıcı isteği üzerine 2026 olarak kalmıştır
    start_date = datetime(2026, 2, 19).date()
    end_date = datetime(2026, 3, 19).date()
    
    if now < start_date:
        kalan = (start_date - now).days
        mesaj = (
            f"⏳ <b>RAMAZAN'A DOĞRU</b>\n\n"
            f"On bir ayın sultanına kavuşmaya son:\n"
            f"🌙 <b>{kalan} GÜN</b> kaldı.\n\n"
            f"<i>Hazırlıklar başlasın, gönüller şenlensin!</i>"
        )
    elif now > end_date:
        mesaj = (
            "👋 <b>ELVEDA YA ŞEHR-İ RAMAZAN</b>\n\n"
            "Mübarek Ramazan ayı sona erdi.\n"
            "<i>Rabbim tekrarına kavuşturmayı nasip eylesin. Bayramımız mübarek olsun.</i>"
        )
    else:
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN TAKVİMİ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Bugün Ramazan-ı Şerif'in:\n"
            f"✨ <b>{gun}. Günü</b>\n\n"
            f"<i>“Oruç sabrın yarısıdır.”</i>\n"
            f"Rabbim ibadetlerinizi dergahında kabul eylesin."
        )
        
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# ==========================
# GÜNCELLENMİŞ HADİS KOMUTU
# ==========================
async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("⚠️ <i>Sistemde şu an yüklü hadis bulunamadı.</i>", parse_mode=ParseMode.HTML)
        return

    secilen = random.choice(HADISLER)
    
    mesaj = (
        "📜 <b>BİR HADİS-İ ŞERİF</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>“{secilen['metin']}”</i>\n\n"
        f"📚 <b>Kaynak:</b> {secilen['kaynak']}"
    )
    
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

# ==========================
# BOTU BAŞLATMA
# ==========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kaydet_mesaj_chat))
    print("Bot başarıyla başlatıldı ve çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
