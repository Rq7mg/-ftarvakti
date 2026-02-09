import json
import random
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# --------------------------
# Ayarlar
# --------------------------
HADIS_DOSYA = "hadisler.json"      # JSON dosyanın yolu
USED_HADIS_DOSYA = "used_hadis.json"  # Gösterilen hadisleri saklamak için (Heroku restart sonrası hatırlamak için)
ADMINS = [6563936773]               # Telegram admin ID'lerini buraya ekle

# --------------------------
# JSON yükleme ve kaydetme
# --------------------------
def load_json(dosya):
    try:
        with open(dosya, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_json(dosya, data):
    with open(dosya, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Hadisleri ve gösterilenleri yükle
HADISLER = load_json(HADIS_DOSYA)
USED_HADIS = load_json(USED_HADIS_DOSYA)

# --------------------------
# /hadis komutu
# --------------------------
async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USED_HADIS

    if not HADISLER:
        await update.message.reply_text("⚠️ Hadis bulunamadı.")
        return

    # Tüm hadisler gösterildiyse sıfırla
    if len(USED_HADIS) == len(HADISLER):
        USED_HADIS = []

    # Kullanılmayan hadislerden seç
    kalan = [h for h in HADISLER if h not in USED_HADIS]
    secilen = random.choice(kalan)
    USED_HADIS.append(secilen)
    save_json(USED_HADIS_DOSYA, USED_HADIS)  # Heroku restart sonrası kaybolmaması için

    mesaj = f"📜 Hadis-i Şerif\n🕌 Ramazan Botu\n\n“{secilen['metin']}”\n\nKaynak: {secilen['kaynak']}"
    await update.message.reply_text(mesaj)

# --------------------------
# /eklehadis komutu (sadece admin)
# Kullanım: /eklehadis Hadis metni | Kaynak
# --------------------------
async def eklehadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("⚠️ Bu komutu sadece admin kullanabilir.")
        return

    args = update.message.text.split(" ", 1)
    if len(args) < 2 or "|" not in args[1]:
        await update.message.reply_text("Kullanım: /eklehadis Hadis metni | Kaynak")
        return

    metin, kaynak = [x.strip() for x in args[1].split("|", 1)]
    yeni_hadis = {"metin": metin, "kaynak": kaynak}
    HADISLER.append(yeni_hadis)
    save_json(HADIS_DOSYA, HADISLER)

    await update.message.reply_text(f"✅ Hadis eklendi:\n“{metin}”\nKaynak: {kaynak}")

# --------------------------
# Handler kayıt fonksiyonu
# --------------------------
def register_handlers(dp):
    dp.add_handler(CommandHandler("hadis", hadis))
    dp.add_handler(CommandHandler("eklehadis", eklehadis))
