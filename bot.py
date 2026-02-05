# --------------------------
# Türkçe karakterleri normalize et
# --------------------------
def normalize(text):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return text.translate(tr_map).lower()

# --------------------------
# /iftar
# --------------------------
async def iftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /iftar <şehir>")
        return

    city_input = context.args[0]
    city = normalize(city_input)  # Normalize edildi
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
            f"📍 {city_input.title()}\n🍽️ İftara {hours} saat {minutes} dakika kaldı ({saat})"
        )
    else:
        await update.message.reply_text(
            f"📍 {city_input.title()}\n🌙 İftar vakti geçti, bir sonraki vakit: {saat}"
        )

# --------------------------
# /sahur
# --------------------------
async def sahur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Kullanım: /sahur <şehir>")
        return

    city_input = context.args[0]
    city = normalize(city_input)  # Normalize edildi
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
        f"📍 {city_input.title()}\n🌙 Sahura {hours} saat {minutes} dakika kaldı ({saat})"
    )
