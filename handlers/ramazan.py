from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import pytz

# Ramazan başlangıç tarihi
RAMAZAN_START = datetime(2026, 3, 12)  # bunu her yıl güncelle

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz).date()

    start = RAMAZAN_START.date()
    end = start + timedelta(days=30)

    if now < start:
        kalan = (start - now).days
        await update.message.reply_text(f"🌙 Ramazan’a {kalan} gün kaldı.")
        return

    if now >= end:
        await update.message.reply_text("🌙 Bu yılki Ramazan sona erdi.")
        return

    gun = (now - start).days + 1
    await update.message.reply_text(f"🌙 Bugün Ramazan’ın {gun}. günü.")
