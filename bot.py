import os
import asyncio
import logging
import aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Log ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- AYARLAR ---
TOKEN = os.getenv("BOT_TOKEN")
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))
CHECK_INTERVAL = 600   # 10 dakikada bir kontrol

# Takip edilecek hesaplar kümesi
tracked_accounts = {
    "instagram": set(),
    "tiktok": set()
}

# --- PROFIL DURUMU KONTROL ETME ---
async def is_account_active(platform: str, username: str) -> bool:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    if platform == "instagram":
        url = f"https://www.instagram.com/{username}/"
    elif platform == "tiktok":
        url = f"https://www.tiktok.com/@{username}"
    else:
        return False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, allow_redirects=True, timeout=10) as response:
                if response.status != 200:
                    return False
                
                html = await response.text()
                html_lower = html.lower()
                
                if platform == "instagram":
                    error_phrases = [
                        "sorry, this page isn't available",
                        "the link you followed may be broken",
                        "bu sayfaya ulaşılamıyor",
                        "girdiğiniz bağlantı bozuk",
                        "click to load",
                        "deactivated",
                        "suspended",
                        "kapatıldı",
                        "bulunamadı"
                    ]
                    for phrase in error_phrases:
                        if phrase in html_lower:
                            return False
                    
                    if "log in" in html_lower and "sign up" in html_lower and f"@{username}" not in html_lower:
                        return False

                    return True
                    
                elif platform == "tiktok":
                    error_phrases = [
                        "couldn't find this account",
                        "account suspended",
                        "kullanıcı bulunamadı",
                        "hesap askıya alındı"
                    ]
                    for phrase in error_phrases:
                        if phrase in html_lower:
                            return False
                    return True
                    
                return False
    except Exception as e:
        logging.error(f"Hata oluştu ({platform} - {username}): {e}")
        return False

# --- ARKA PLAN DÖNGÜSÜ ---
async def monitor_accounts(app):
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        
        for platform in list(tracked_accounts.keys()):
            for username in list(tracked_accounts[platform]):
                active = await is_account_active(platform, username)
                
                if active:
                    msg = f"🎉 **MÜJDE! HESAP AÇILDI** 🎉\n\nPlatform: **{platform.upper()}**\nKullanıcı Adı: `@{username}`\n\nHesap tekrar aktif duruma geldi!"
                    await app.bot.send_message(chat_id=MY_CHAT_ID, text=msg, parse_mode="Markdown")
                    tracked_accounts[platform].remove(username)

# --- TELEGRAM KOMUTLARI ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_CHAT_ID:
        await update.message.reply_text("⛔ Bu bot özeldir, sadece sahibi kullanabilir.")
        return

    await update.message.reply_text(
        "👋 **Yasaklı Hesap Takip Botuna Hoş Geldiniz!**\n\n"
        "Komutlar:\n"
        "`/ekle instagram kullanıcı_adı` - IG hesabı takibe alır.\n"
        "`/ekle tiktok kullanıcı_adı` - TikTok hesabı takibe alır.\n"
        "`/liste` - Takip edilen hesapları gösterir."
    )

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_CHAT_ID:
        return

    if len(context.args) < 2:
        await update.message.reply_text("Kullanım: `/ekle instagram kullanıcı_adı`", parse_mode="Markdown")
        return

    platform = context.args[0].lower()
    username = context.args[1].replace("@", "").strip()

    if platform not in ["instagram", "tiktok"]:
        await update.message.reply_text("Lütfen platform olarak sadece `instagram` veya `tiktok` belirtin.")
        return

    tracked_accounts[platform].add(username)
    await update.message.reply_text(f"✅ **{platform.capitalize()}** hesabı `@{username}` takip listesine eklendi.", parse_mode="Markdown")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_CHAT_ID:
        return

    msg = "📋 **Takip Edilen Yasaklı Hesaplar:**\n\n"
    msg += f"📸 **Instagram:** {', '.join(tracked_accounts['instagram']) if tracked_accounts['instagram'] else 'Yok'}\n"
    msg += f"🎵 **TikTok:** {', '.join(tracked_accounts['tiktok']) if tracked_accounts['tiktok'] else 'Yok'}"
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- UPTIMEROBOT WEB SUNUCUSU ---
async def handle_ping(request):
    return web.Response(text="Telegram Bot is active and running!")

# --- ANA DÖNGÜ ---
async def main():
    if not TOKEN or not MY_CHAT_ID:
        logging.error("HATA: BOT_TOKEN veya MY_CHAT_ID çevre değişkenleri eksik!")
        return

    web_app = web.Application()
    web_app.router.add_get("/", handle_ping)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web sunucusu {PORT} portunda çalışıyor...")

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('ekle', add_account))
    application.add_handler(CommandHandler('liste', list_accounts))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logging.info("Telegram botu çalışıyor...")

    await monitor_accounts(application)

if __name__ == '__main__':
    asyncio.run(main())
