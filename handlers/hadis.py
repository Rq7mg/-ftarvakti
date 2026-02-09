import json
import random
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

# --------------------------
# Ayarlar
# --------------------------
HADIS_DOSYA = "hadisler.json"  # Tüm hadisleri içeren JSON dosyası
ADMINS = [6563936773]           # Telegram admin ID'lerini buraya ekle

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

# Hadisleri yükle
HADISLER = load_json(HADIS_DOSYA)

# --------------------------
# /hadis komutu
# --------------------------
async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("⚠️ Hadis bulunamadı.")
        return

    secilen = random.choice(HADISLER)  # tamamen random, filtre yok
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
