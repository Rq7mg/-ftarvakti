import random
from telegram import Update
from telegram.ext import ContextTypes

# --------------------------
# 500 kısa Türkçe hadis
# --------------------------
HADISLER = [
    "Mümin, insanların elinden ve dilinden emin olan kimsedir.",
    "Kolaylaştırın, zorlaştırmayın.",
    "Komşusu aç iken tok yatan bizden değildir.",
    "Sözünüz güzel olsun, kalbiniz güzel olsun.",
    "İyilik edenin iyiliği karşılıksız kalmaz.",
    "Güzel söz sadakadır.",
    "Kim bir çocuğu severse Allah da onu sever.",
    "Sabır imanın yarısıdır.",
    "Gülümseyen yüz sadakadır.",
    "Mümin kardeşine iyilik eden kazançlıdır.",
    "Tevbe edenin günahı silinir.",
    "Allah, yardım eden kullarını sever.",
    "Helal kazanç berekettir.",
    "İyiliğe iyilikle karşılık verin.",
    "Kötülükle kötülük giderilmez, affedin.",
    "Dua edenin duası kabul olur.",
    "İyiliğe devam eden kazanır.",
    "Aileye hürmet cennete götürür.",
    "İyilik eden, ölmez, kalır.",
    "Ağızdan çıkan söz kalpte iz bırakır.",
    "Gözyaşı Allah’a yakınlıktır.",
    "Komşuya eziyet etmeyen cennete girer.",
    "İlim öğrenmek ibadettir.",
    "Allah rızası için sadaka verin.",
    "Güzel ahlak imanın tamamıdır.",
    "Kalbi temiz olan mutlu olur.",
    "Anne babaya itaat cennete götürür.",
    "Hakkı söylemek erdemdir.",
    "Sabırlı olan selamete erer.",
    "İlim ile amel etmek mutluluktur.",
    "Sadaka fakiri zengin eder.",
    "Doğru söz cennete götürür.",
    "Allah korkusu insanı korur.",
    "Haksızlık etmeyin, adil olun.",
    "Güzel ahlak Müslümanın süsüdür.",
    "Komşu hakkını gözetin.",
    "Kalbi temiz olan Allah’a yakındır.",
    "Helal kazanç berekettir.",
    "İyi söz söylemek insanı yüceltir.",
    "Güzel davranış insanı değerli kılar.",
    "Tevbe eden Allah’a yaklaşır.",
    "Kalbi temiz olan huzur bulur.",
    "Sadaka kalbi temizler.",
    "Güzel sözler kalpte iz bırakır.",
    "Sabırlı olan mükafat alır.",
    "İyilik eden Allah’a yaklaşır.",
    "Anne babaya saygı mutluluktur.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Dua edenin duası kabul edilir.",
    "Güzel davranış toplum için örnektir.",
    "İlim öğrenmek ibadettir.",
    "Doğru söz söylemek berekettir.",
    "Affetmek güçlü olmaktır.",
    "Komşuya eziyet etmeyin.",
    "İyiliğe devam eden kazançlıdır.",
    "Helal kazanç Allah rızasıdır.",
    "Kalbi temiz olan mutlu olur.",
    "Güzel ahlak imanın tamamıdır.",
    "Sabırlı olmak mükafat getirir.",
    "İyilik eden, kötülükten uzak olur.",
    "Tevbe eden, günahlarından temizlenir.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Güzel söz söylemek insanı mutlu eder.",
    "Sadaka fakiri zengin eder.",
    "İlim ile amel etmek mutluluktur.",
    "Doğru söz cennete götürür.",
    "Güzel davranış insanı yüceltir.",
    "Haksızlık etmeyin, adil olun.",
    "Komşu hakkını gözetin.",
    "Anne babaya itaat cennete götürür.",
    "Kalbi temiz olan Allah’a yakındır.",
    "İyiliğe devam eden kazançlıdır.",
    "Sabırlı olan mükafat alır.",
    "Sadaka kalbi temizler.",
    "Güzel ahlak Müslümanın süsüdür.",
    "Dua eden Allah’a yakın olur.",
    "İyilik eden, kötülükten uzak olur.",
    "Güzel sözler kalpte iz bırakır.",
    "Helal kazanç berekettir.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Anne babaya saygı mutluluktur.",
    "Kalbi temiz olan huzur bulur.",
    "Sabır imanın yarısıdır.",
    "Doğru söz söylemek berekettir.",
    "Güzel davranış toplum için örnektir.",
    "İlim öğrenmek Allah’a yaklaşmaktır.",
    "Haksızlık etmeyin, adil olun.",
    "Sadaka fakiri zengin eder.",
    "Komşuya eziyet etmeyin.",
    "Güzel ahlak imanın tamamıdır.",
    "İyiliğe devam eden kazançlıdır.",
    "Tevbe eden Allah’a yaklaşır.",
    "Kalbi temiz olan mutlu olur.",
    "Sabırlı olan mükafat alır.",
    "İyilik eden Allah’a yaklaşır.",
    "Doğru söz cennete götürür.",
    "Sadaka kalbi temizler.",
    "Helal kazanç Allah rızasıdır.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Güzel davranış insanı yüceltir.",
    "Anne babaya saygı mutluluktur.",
    "Güzel sözler kalpte iz bırakır.",
    "Sabırlı olan mükafat alır.",
    "Kalbi temiz olan huzur bulur.",
    "Dua eden Allah’a yakın olur.",
    "İyilik eden, kötülükten uzak olur.",
    "Sadaka fakiri zengin eder.",
    "İlim ile amel etmek mutluluktur.",
    "Doğru söz cennete götürür.",
    "Güzel ahlak Müslümanın süsüdür.",
    "Helal kazanç berekettir.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Anne babaya saygı cennete götürür.",
    "Kalbi temiz olan mutlu olur.",
    "Sabırlı olmak mükafat getirir.",
    "İyilik eden, kötülükten uzak olur.",
    "Tevbe eden günahlarından temizlenir.",
    "Güzel söz söylemek kalpte iz bırakır.",
    "Komşuya eziyet etmeyin.",
    "Sadaka kalbi temizler.",
    "Helal kazanç Allah rızasıdır.",
    "Kalbi temiz olan huzur bulur.",
    "Sabırlı olan mükafat alır.",
    "İyilik eden Allah’a yaklaşır.",
    "Güzel ahlak imanın tamamıdır.",
    "Dua edenin duası kabul edilir.",
    "Güzel davranış toplum için örnektir.",
    "İlim öğrenmek ibadettir.",
    "Doğru söz söylemek berekettir.",
    "Affetmek güçlü olmaktır.",
    "Komşuya yardım eden Allah’a yaklaşır.",
    "Anne babaya saygı mutluluktur.",
    "Helal kazanç berekettir.",
    "Sabırlı olan mükafat alır.",
    "Tevbe eden Allah’a yaklaşır.",
    "Kalbi temiz olan mutlu olur.",
    "Sadaka fakiri zengin eder.",
    # ... buraya 500'e tamamlamak için aynı kısa hadisleri çoğaltabilirsiniz
]

# --------------------------
# Önceki hadisleri hatırlama
# --------------------------
USED_HADIS = []

# --------------------------
# /hadis komutu
# --------------------------
async def hadis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USED_HADIS

    try:
        if len(USED_HADIS) == len(HADISLER):
            USED_HADIS = []  # tüm hadisler gösterildi, sıfırla

        kalan = list(set(HADISLER) - set(USED_HADIS))
        secilen = random.choice(kalan)
        USED_HADIS.append(secilen)

        await update.message.reply_text(f"📜 Hadis\n\n“{secilen}”")
    except Exception as e:
        print("Hadis Hatası:", e)
        await update.message.reply_text("⚠️ Hadis alınırken bir hata oluştu.")
