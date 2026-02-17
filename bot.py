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

# Admin ID'leri (Duyuru komutu için)
ADMIN_IDS = [6563936773, 6030484208]
CHAT_FILE = "chats.json"
HADIS_DOSYA = "hadisler.json"

# =========================
# 1. VERİ YÖNETİMİ
# =========================

def load_json(dosya):
    """JSON dosyasını güvenli şekilde yükler."""
    try:
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

HADISLER = load_json(HADIS_DOSYA)

def get_all_chats():
    """Kayıtlı tüm sohbetleri getirir."""
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return []
    return []

def kaydet_chat_id(chat_id, chat_type):
    """Yeni bir sohbet varsa veritabanına kaydeder."""
    try:
        chats = get_all_chats()
        # Eğer chat_id listede yoksa ekle
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
    """Türkçe karakterleri İngilizce'ye çevirir (API için)."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower()

def find_location_id(city):
    """Diyanet API'sinden şehir ID'sini bulur."""
    try:
        url = f"https://prayertimes.api.abdus.dev/api/diyanet/search?q={city}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data[0].get("id") if data else None
    except:
        return None

def get_prayertimes(location_id):
    """Şehir ID'sine göre vakitleri çeker."""
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
    """Kalan süreyi hesaplar."""
    now = datetime.now(tz)
    h, m = map(int, vakit_str.split(":"))
    vakit_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
    
    if next_day_if_passed and now >= vakit_time:
        vakit_time += timedelta(days=1)
        
    delta = vakit_time - now
    total_minutes = int(delta.total_seconds() / 60)
    return total_minutes // 60, total_minutes % 60, vakit_time.strftime("%H:%M")

# =========================
# 3. OTOMATİK GÖREVLER (JOB QUEUE)
# =========================

async def otomatik_hadis_paylas(context: ContextTypes.DEFAULT_TYPE):
    """Her 6 saatte bir GRUPLARA hadis atar."""
    if not HADISLER:
        return

    chats = get_all_chats()
    secilen = random.choice(HADISLER)
    
    mesaj = (
        "✨ <b>GÜNÜN MANEVİ HATIRLATMASI</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>“{secilen['metin']}”</i>\n\n"
        f"📚 <b>Kaynak:</b> {secilen['kaynak']}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🕊 <i>Hayırlı vakitler dileriz.</i>"
    )

    for chat in chats:
        # FİLTRE: Sadece 'group' veya 'supergroup' ise gönder.
        # Özel mesajlara (private) gönderme.
        if chat.get("type") in ["group", "supergroup"]:
            try:
                await context.bot.send_message(chat["chat_id"], mesaj, parse_mode=ParseMode.HTML)
                # Telegram limitlerine takılmamak için minik bekleme
                await asyncio.sleep(0.05) 
            except Exception as e:
                # Bot gruptan atılmış olabilir, hatayı yoksay
                continue

# =========================
# 4. BOT KOMUTLARI
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    
    mesaj = (
        "<b>🌙 Hoş Geldiniz, Kıymetli Gönül Dostu!</b>\n\n"
        "Ramazan-ı Şerif'in maneviyatını birlikte yaşamak için buradayız. "
        "Botumuz gruplarda otomatik hadis paylaşır ve ibadet vakitlerini takip etmenizi sağlar.\n\n"
        "👇 <b>Hızlı Menü:</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🍽 <b>/iftar &lt;şehir&gt;</b> : İftar vaktini ve duasını gösterir.\n"
        "🥣 <b>/sahur &lt;şehir&gt;</b> : Sahur vaktini ve niyetini gösterir.\n"
        "📜 <b>/hadis</b> : Rastgele bir hadis-i şerif okuyun.\n"
        "📅 <b>/ramazan</b> : Ramazan takvimi ve geri sayım.\n"
        "📢 <b>/duyuru</b> : (Admin) Toplu mesaj sistemi.\n\n"
        "<i>🤲 Rabbim ibadetlerinizi kabul eylesin.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <i>Lütfen şehir adı giriniz. Örnek:</i> <code>/iftar Istanbul</code>", parse_mode=ParseMode.HTML)
        return
    
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    
    if not loc_id:
        await update.message.reply_text("🚫 <b>Şehir bulunamadı.</b> Lütfen Türkçe karakter kullanmadan deneyin (örn: Istanbul).", parse_mode=ParseMode.HTML)
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

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ <i>Lütfen şehir adı giriniz. Örnek:</i> <code>/sahur Ankara</code>", parse_mode=ParseMode.HTML)
        return
        
    city_input = context.args[0]
    loc_id = find_location_id(normalize(city_input))
    
    if not loc_id:
        await update.message.reply_text("🚫 <b>Şehir bulunamadı.</b>", parse_mode=ParseMode.HTML)
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
        f"🤲 <i>Hayırlı sahurlar dileriz.</i>"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(tz).date()
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
            "<i>Bayramınız mübarek olsun.</i>"
        )
    else:
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN TAKVİMİ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Bugün Ramazan-ı Şerif'in:\n"
            f"✨ <b>{gun}. Günü</b>\n\n"
            f"<i>“Oruç sabrın yarısıdır.”</i>"
        )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("⚠️ <i>Sistemde yüklü hadis bulunamadı.</i>", parse_mode=ParseMode.HTML)
        return

    secilen = random.choice(HADISLER)
    mesaj = (
        "📜 <b>BİR HADİS-İ ŞERİF</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>“{secilen['metin']}”</i>\n\n"
        f"📚 <b>Kaynak:</b> {secilen['kaynak']}"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def duyuru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Sadece adminler kullanabilir
    if update.message.from_user.id not in ADMIN_IDS:
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("❗ Duyuru için bir mesaja yanıt vermelisiniz.")
        return

    reply = update.message.reply_to_message
    chats = get_all_chats()
    basarili = 0
    header_text = "📢 <b>RAMAZAN DUYURUSU</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

    for chat in chats:
        try:
            if reply.text:
                await context.bot.send_message(chat["chat_id"], f"{header_text}{reply.text}", parse_mode=ParseMode.HTML)
            elif reply.photo:
                await context.bot.send_photo(
                    chat["chat_id"], 
                    photo=reply.photo[-1].file_id, 
                    caption=f"{header_text}{reply.caption}" if reply.caption else header_text,
                    parse_mode=ParseMode.HTML
                )
            elif reply.video:
                await context.bot.send_video(
                    chat["chat_id"],
                    video=reply.video.file_id,
                    caption=f"{header_text}{reply.caption}" if reply.caption else header_text,
                    parse_mode=ParseMode.HTML
                )
            basarili += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await update.message.reply_text(f"✅ Duyuru {basarili} sohbete gönderildi.")

async def kaydet_mesaj_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Herhangi bir mesaj geldiğinde sohbeti veritabanına kaydeder."""
    if update.message:
        kaydet_chat_id(update.message.chat_id, update.message.chat.type)

# =========================
# 5. MAIN (BAŞLATMA)
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ---------------------------
    # ZAMANLAYICIYI KURUYORUZ
    # ---------------------------
    job_queue = app.job_queue
    # 21600 saniye = 6 saat. 
    # first=10 -> Bot başladıktan 10 saniye sonra ilk mesajı dener (test için iyi), sonra döngüye girer.
    job_queue.run_repeating(otomatik_hadis_paylas, interval=21600, first=10)

    # Handler'ları ekle
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("duyuru", duyuru))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    
    # Text handler en sonda olmalı
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kaydet_mesaj_chat))
    
    print("Bot çalışıyor... (6 saatlik grup döngüsü aktif)")
    app.run_polling()

if __name__ == "__main__":
    main()
