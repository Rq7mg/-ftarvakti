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

# =========================
# AYARLAR (Config)
# =========================
# TOKEN'ı ortam değişkenlerinden (Environment Variables) çeker. 
# Eğer direkt buraya yazacaksan: TOKEN = "SENIN_TOKEN_BURAYA"
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
    except: pass
    return []

HADISLER = load_json(HADIS_DOSYA)

def get_all_chats():
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except: return []
    return []

def kaydet_chat_id(chat_id, chat_type):
    try:
        chats = get_all_chats()
        if not any(c["chat_id"] == chat_id for c in chats):
            chats.append({"chat_id": chat_id, "type": chat_type})
            with open(CHAT_FILE, "w", encoding="utf-8") as f:
                json.dump(chats, f)
    except: pass

# =========================
# 2. GLOBAL CANLI VAKİT ÇEKME (API)
# =========================

def get_prayertimes(city):
    """
    Dünyadaki tüm şehirleri adres bazlı arar. Saçma bir yerse None döner.
    """
    try:
        # timingsByAddress metodu kullanarak tüm dünyada arama yapıyoruz
        url = f"https://api.aladhan.com/v1/timingsByAddress?address={city}"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        # Eğer API 200 (Başarılı) döndürdüyse ve data içi doluysa
        if r.status_code == 200 and data.get("code") == 200:
            timings = data["data"]["timings"]
            tz_name = data["data"]["meta"]["timezone"] # O şehrin saat dilimi (Örn: Europe/Istanbul veya America/New_York)
            return timings, tz_name
        else:
            return None, None
            
    except Exception as e:
        print(f"API Mevzusu Patladı: {e}")
        return None, None

def time_until(vakit_str, tz_name):
    """
    O şehrin yerel saat dilimine göre ne kadar kaldığını hesaplar.
    """
    if not vakit_str or not tz_name: return 0, 0, "--:--"
    
    # Şehrin kendi saat dilimini al
    target_tz = pytz.timezone(tz_name)
    now_local = datetime.now(target_tz)
    
    # Gelen veri bazen "18:45 (EEST)" formatında olabilir, sadece saati alıyoruz
    clean_time = vakit_str.split(" ")[0]
    h, m = map(int, clean_time.split(":"))
    
    vakit_time = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    
    # Eğer vakit geçmişse, yarına (ertesi güne) hesapla
    if now_local >= vakit_time:
        vakit_time += timedelta(days=1)
        
    delta = vakit_time - now_local
    total_seconds = int(delta.total_seconds())
    return total_seconds // 3600, (total_seconds % 3600) // 60, clean_time

# =========================
# 3. ANKARA ŞİVELİ KOMUTLAR
# =========================

async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ **La bebe hangi şehrin iftarını soruyon?**\nÖrn: `/iftar ankara` yaz hele.", parse_mode=ParseMode.HTML)
        return
    
    city = " ".join(context.args)
    timings, tz_name = get_prayertimes(city)
    
    # HATA DURUMU: ŞEHİR BULUNAMADI (Ankara Atarı + Ramazan Kutlaması)
    if not timings:
        hata_mesaji = (
            f"❌ **La bebe sen beni mi koparıyon? '{city}' diye bi memleket mi var haritada!**\n"
            f"İcat çıkarma başıma, uyduruk isimler yazıp durma şuraya. Adam akıllı bir şehir yaz da vaktini söyleyek!\n\n"
            f"🌙 *Neyse... Yine de mübarek Ramazan ayındayız, kalbini kırmayım gardaşım. "
            f"Rabbim niyetini kabul etsin, Ramazan-ı Şerif'in mübarek olsun. Hadi şimdi düzgün bi şehir yaz da gel.*"
        )
        await update.message.reply_text(hata_mesaji, parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Maghrib"], tz_name)
    mesaj = (
        f"🕌 <b>İFTAR VAKTİ | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"🕓 <b>Akşam Ezanı:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"🤲 <b>İftar Duası:</b>\n"
        f"<i>'Allah'ım senin rızan için oruç tuttum, senin rızkınla orucumu açıyorum.'</i>\n\n"
        f"✨ <b>Hayırlı İftarlar Gardaşım...</b>\n"
        f"Çömelin sofraya, ezana az kaldı! 🥖"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ **Sahur vaktini merak ediyon ama şehir yazmıyon la bebe...**", parse_mode=ParseMode.HTML)
        return
        
    city = " ".join(context.args)
    timings, tz_name = get_prayertimes(city)
    
    if not timings:
        hata_mesaji = (
            f"❌ **Oğlum '{city}' neresi la? Uzayda falan mı arıyon sahuru!**\n"
            f"Böyle bi yer yok sistemde. Beni boşuna yorma.\n\n"
            f"🌙 *Neyse, mübarek ayda sinirlenmeyecem. Gecen feyizli, sahurun bereketli, Ramazan'ın mübarek olsun gardaşım. "
            f"Düzgün bi yer yaz da vaktini veriyim sana.*"
        )
        await update.message.reply_text(hata_mesaji, parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Fajr"], tz_name)
    mesaj = (
        f"🌌 <b>SAHUR (İMSAK) | {city.upper()}</b>\n"
        f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
        f"📢 <b>İmsak Vakti:</b> <code>{saat}</code>\n"
        f"⏳ <b>Kalan Süre:</b> <b>{h} saat {m} dakika</b>\n\n"
        f"💡 <b>Niyet:</b>\n"
        f"<i>'Niyet ettim Allah rızası için bugünkü Ramazan orucunu tutmaya.'</i>\n\n"
        f"🤲 <b>Bereketli Sahurlar La Bebe.</b>\n"
        f"Suyu kana kana iç, sonra yanarsın! 💧"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bugünün tarihini sabit Türkiye saatine göre alıyoruz (genel bilgi için)
    now = datetime.now(pytz.timezone("Europe/Istanbul")).date()
    start_date = datetime(2026, 2, 19).date()
    end_date = datetime(2026, 3, 19).date()
    
    if now < start_date:
        kalan = (start_date - now).days
        mesaj = f"⏳ <b>RAMAZAN'A KAVUŞMAYA</b>\n\n🌙 On bir ayın sultanına son <b>{kalan} gün</b> kaldı gardaş!"
    elif now > end_date:
        mesaj = "👋 <b>Elveda Ya Şehr-i Ramazan...</b>\n\nRabbim tekrarına kavuştursun la bebe."
    else:
        gun = (now - start_date).days + 1
        mesaj = (
            f"🌙 <b>RAMAZAN-I ŞERİF</b>\n"
            f"┈┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┈\n\n"
            f"🗓 Bugün Ramazan'ın <b>{gun}. günü</b>.\n\n"
            f"<i>Rabbim oruçlarınızı makbul eylesin, dualarda bizi unutmayın.</i>"
        )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kaydet_chat_id(update.message.chat_id, update.message.chat.type)
    mesaj = (
        "<b>🌙 Hoş Geldin Gardaş!</b>\n\n"
        "Ramazan rehberin emrine amade. Şehir yaz, vaktini kap! Dünyanın neresinde olursan ol bulurum.\n\n"
        "🍽 /iftar <code>şehir</code>\n"
        "🥣 /sahur <code>şehir</code>\n"
        "📜 /hadis\n"
        "📅 /ramazan"
    )
    await update.message.reply_text(mesaj, parse_mode=ParseMode.HTML)

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not HADISLER:
        await update.message.reply_text("📜 <i>Sabır müminin zırhıdır gardaş.</i>", parse_mode=ParseMode.HTML)
        return
    secilen = random.choice(HADISLER)
    await update.message.reply_text(f"📜 <b>GÜNÜN HADİSİ</b>\n\n<i>“{secilen['metin']}”</i>\n\n📚 {secilen['kaynak']}", parse_mode=ParseMode.HTML)

# =========================
# 4. SİSTEM ÇALIŞTIRMA
# =========================

def main():
    if not TOKEN:
        print("TOKEN Bulunamadı! Mevzu patlak. Lütfen .env dosyanı veya TOKEN ayarını kontrol et.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    # Komutları Ekliyoruz
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    
    print("Bot marşa bastı, tüm dünya radarda, Ankara sokaklarında dolanıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
