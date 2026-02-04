from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
import pytz

# Ramazan Türkiye için
RAMAZAN_START = datetime(2026, 2, 19)  # 19 Şubat 2026 Perşembe
RAMAZAN_END = datetime(2026, 3, 19)    # 19 Mart 2026 Perşembe

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tz = pytz.timezone("Europe/Istanbul")
    now = datetime.now(tz).date()

    start = RAMAZAN_START.date()
    end = RAMAZAN_END.date()

    # Ramazan başlamadıysa
    if now < start:
        kalan = (start - now).days
        await update.message.reply_text(f"🌙 Ramazan’a {kalan} gün kaldı.")
        return

    # Ramazan bitti
    if now > end:
        await update.message.reply_text("🌙 Bu yılki Ramazan sona erdi. Allah kabul etsin 🤲")
        return

    # Ramazan içindeysek
    gun = (now - start).days + 1
    await update.message.reply_text(f"🌙 Bugün Ramazan’ın {gun}. günü.")
