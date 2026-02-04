import random
import requests
from telegram import Update
from telegram.ext import ContextTypes

# Ücretsiz hadis API’si ve çeviri
def get_random_hadis():
    url = "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions/eng-bukhari.json"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    hadisler = data.get("hadiths", [])
    return random.choice(hadisler)["text"]

def translate_to_tr(text):
    url = "https://libretranslate.de/translate"
    payload = {"q": text, "source": "en", "target": "tr", "format": "text"}
    r = requests.post(url, data=payload, timeout=15)
    r.raise_for_status()
    return r.json()["translatedText"]

async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        en_hadis = get_random_hadis()
        tr_hadis = translate_to_tr(en_hadis)

        await update.message.reply_text(
            "📜 Hadis\n\n"
            f"“{tr_hadis}”\n\n"
            "📘 Kaynak: Buhari"
        )
    except Exception as e:
        await update.message.reply_text("⚠️ Hadis alınırken bir hata oluştu.")
        print("Hadis Hatası:", e)
