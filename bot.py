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
# 2. RADARLI VE DÜNYA ÇAPINDA VAKİT ÇEKME
# =========================

def get_prayertimes(city):
    """
    Önce OpenStreetMap ile yerin gerçekte var olup olmadığını teyit eder.
    Varsa koordinatlarını alıp Diyanet/Aladhan API'sine yollar.
    """
    try:
        # 1. Aşama: Haritada yer teyidi (Uyduruk şehirleri engeller)
        headers = {'User-Agent': 'KiyiciZeminBot/1.0'}
        geo_url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
        geo_req = requests.get(geo_url, headers=headers, timeout=10)
        geo_data = geo_req.json()

        if not geo_data:
            # Haritada yoksa direkt mevzuyu patlat!
            return None, None, None

        # Haritada bulduysa koordinatlarını ve gerçek adını al
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
        gercek_yer = geo_data[0]['display_name'].split(",")[0] # Orijinal şehir adını alır

        # 2. Aşama: Gerçek koordinatlarla saati çek
        aladhan_url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=13"
        r = requests.get(aladhan_url, timeout=10)
        data = r.json()
        
        if r.status_code == 200 and data.get("code") == 200:
            timings = data["data"]["timings"]
            tz_name = data["data"]["meta"]["timezone"]
            return timings, tz_name, gercek_yer
        else:
            return None, None, None
            
    except Exception as e:
        print(f"Sistem Tıkandı Gardaş: {e}")
        return None, None, None

def time_until(vakit_str, tz_name):
    if not vakit_str or not tz_name: return 0, 0, "--:--"
    
    target_tz = pytz.timezone(tz_name)
    now_local = datetime.now(target_tz)
    
    clean_time = vakit_str.split(" ")[0]
    h, m = map(int, clean_time.split(":"))
    
    vakit_time = now_local.replace(hour=h, minute=m, second=0, microsecond=0)
    
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
    timings, tz_name, gercek_yer = get_prayertimes(city)
    
    if not timings:
        hata_mesaji = (
            f"❌ **La bebe sen beni mi koparıyon? '{city}' diye bi memleket mi var haritada!**\n"
            f"İcat çıkarma başıma, uyduruk isimler yazıp durma şuraya. Adam akıllı bir şehir yaz da vaktini söyleyek!\n\n"
            f"🌙 *Neyse... Yine de mübarek Ramazan ayındayız, kalbini kırmayım gardaşım. "
            f"Rabbim niyetini kabul etsin, Ramazan-ı Şerif'in mübarek olsun. Hadi şimdi düzgün bi yer yaz da gel.*"
        )
        await update.message.reply_text(hata_mesaji, parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Maghrib"], tz_name)
    mesaj = (
        f"🕌 <b>İFTAR VAKTİ | {gercek_yer.upper()}</b>\n"
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
    timings, tz_name, gercek_yer = get_prayertimes(city)
    
    if not timings:
        hata_mesaji = (
            f"❌ **Oğlum '{city}' neresi la? Uzayda falan mı arıyon sahuru!**\n"
            f"Böyle bi yer yok sistemde. Haritayı baştan çizdirme bana, beni boşuna yorma.\n\n"
            f"🌙 *Neyse, mübarek ayda sinirlenmeyecem. Gecen feyizli, sahurun bereketli, Ramazan'ın mübarek olsun gardaşım. "
            f"Düzgün bi yer yaz da vaktini veriyim sana.*"
        )
        await update.message.reply_text(hata_mesaji, parse_mode=ParseMode.HTML)
        return

    h, m, saat = time_until(timings["Fajr"], tz_name)
    mesaj = (
        f"🌌 <b>SAHUR (İMSAK) | {gercek_yer.upper()}</b>\n"
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
        print("TOKEN Bulunamadı! Mevzu patlak.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iftar", iftar))
    app.add_handler(CommandHandler("sahur", sahur))
    app.add_handler(CommandHandler("ramazan", ramazan))
    app.add_handler(CommandHandler("hadis", hadis))
    
    print("Bot marşa bastı, Radar sistemi aktif. Uyduruk şehirlere af yok...")
    app.run_polling()

if __name__ == "__main__":
    main()
