import static_ffmpeg
static_ffmpeg.add_paths()

import asyncio
import os
import subprocess
import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import FSInputFile, Message
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Render Environment Variables bo'limiga BOT_TOKEN qo'shilganini tekshiring.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ydl_info_opts = {
    'quiet': True,
    'no_warnings': True,
    'format': 'best',
}

def get_video_info(url: str):
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        return ydl.extract_info(url, download=False)

# ---------------------------------------------------------
# 1. START
# ---------------------------------------------------------
@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = (
        "⚡️ <b>FlashFeatures Bot</b>'ga xush kelibsiz!\n\n"
        "<b>Qanday ishlatiladi?</b>\n"
        "1. Menga Instagram yoki YouTube linkini yuboring.\n"
        "2. Men videoni chiqarib berganimdan so'ng, unga <b>Reply (Javob)</b> qilib buyruq bering:\n\n"
        "🔄 <code>/round</code> — Aylana video (Video note) qilish\n"
        "🎵 <code>/audio</code> — MP3 qilib ajratish\n"
        "✂️ <code>/cut 00:05 00:20</code> — Kerakli qismini qirqish\n\n"
        "<i>Eslatma: link orqali to'g'ridan-to'g'ri <code>/thumb [link]</code> yoki <code>/text [link]</code> qilish ham mumkin.</i>"
    )
    await message.reply(text, parse_mode="HTML")

# ---------------------------------------------------------
# 2. YORDAMCHI: Video faylni olish (Reply orqali yoki Link orqali)
# ---------------------------------------------------------
async def get_source_video(message: Message, target_path: str):
    """Xabar reply qilingan videodan yoki linkdan faylni oladi"""
    # 1-holat: Agar videoga Reply qilingan bo'lsa
    if message.reply_to_message and message.reply_to_message.video:
        file_id = message.reply_to_message.video.file_id
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, target_path)
        return True
    
    # 2-holat: Agar link matnda yozilgan bo'lsa
    parts = message.text.split()
    url = None
    for part in parts:
        if part.startswith("http://") or part.startswith("https://"):
            url = part
            break
            
    if url:
        ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': target_path, 'quiet': True}
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        return True
        
    return False

# ---------------------------------------------------------
# 3. /round - AYLANA VIDEO (Reply orqali)
# ---------------------------------------------------------
@dp.message(Command("round"))
async def round_video_cmd(message: Message):
    status_msg = await message.reply("🔄 Aylana video tayyorlanmoqda...")
    uid = message.from_user.id
    raw_video = f"raw_round_{uid}.mp4"
    round_video = f"round_{uid}.mp4"
    
    try:
        success = await get_source_video(message, raw_video)
        if not success or not os.path.exists(raw_video):
            return await status_msg.edit_text("Videoni topib bo'lmadi! Videoga <b>Reply</b> qilib <code>/round</code> deb yozing yoki linkni qo'shib yuboring.", parse_mode="HTML")
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', raw_video, '-t', '60',
            '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=480:480",
            '-c:v', 'libx264', '-c:a', 'aac', round_video
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
        if os.path.exists(round_video):
            await message.reply_video_note(video_note=FSInputFile(round_video))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Aylana video yasashda xatolik yuz berdi.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        for f in [raw_video, round_video]:
            if os.path.exists(f):
                os.remove(f)

# ---------------------------------------------------------
# 4. /audio - MP3 AJRATISH (Reply orqali)
# ---------------------------------------------------------
@dp.message(Command("audio"))
async def audio_video_cmd(message: Message):
    status_msg = await message.reply("🎵 Audio ajratib olinmoqda...")
    uid = message.from_user.id
    raw_video = f"raw_audio_{uid}.mp4"
    audio_file = f"audio_{uid}.mp3"
    
    try:
        success = await get_source_video(message, raw_video)
        if not success or not os.path.exists(raw_video):
            return await status_msg.edit_text("Videoni topib bo'lmadi! Videoga <b>Reply</b> qilib <code>/audio</code> deb yozing.", parse_mode="HTML")
            
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', raw_video,
            '-vn', '-acodec', 'libmp3lame', '-q:a', '2', audio_file
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
        if os.path.exists(audio_file):
            await message.reply_audio(audio=FSInputFile(audio_file))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Audioni chiqarib bo'lmadi.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        for f in [raw_video, audio_file]:
            if os.path.exists(f):
                os.remove(f)

# ---------------------------------------------------------
# 5. /cut - KESISH (Reply orqali: /cut 00:05 00:15)
# ---------------------------------------------------------
@dp.message(Command("cut"))
async def cut_video_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("Format: Videoga reply qilib <code>/cut 00:05 00:20</code> yozing.", parse_mode="HTML")
    
    start_time, end_time = parts[1].strip(), parts[2].strip()
    status_msg = await message.reply(f"✂️ Video {start_time} dan {end_time} gacha kesilmoqda...")
    
    uid = message.from_user.id
    raw_video = f"raw_cut_{uid}.mp4"
    cut_video = f"cut_{uid}.mp4"
    
    try:
        success = await get_source_video(message, raw_video)
        if not success or not os.path.exists(raw_video):
            return await status_msg.edit_text("Videoni topib bo'lmadi! Videoga reply qiling.")
            
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-ss', start_time, '-to', end_time,
            '-i', raw_video, '-c', 'copy', cut_video
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
        if os.path.exists(cut_video):
            await message.reply_video(video=FSInputFile(cut_video))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Videoni kesib bo'lmadi.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        for f in [raw_video, cut_video]:
            if os.path.exists(f):
                os.remove(f)

# ---------------------------------------------------------
# 6. /thumb va /text (Link orqali)
# ---------------------------------------------------------
@dp.message(Command("text"))
async def get_text_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Format: /text <link>")
    url = parts[1].strip()
    status_msg = await message.reply("📝 Matn o'qilmoqda...")
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_video_info, url)
        await status_msg.edit_text(info.get('description', 'Tavsif topilmadi.')[:4000])
    except Exception:
        await status_msg.edit_text("Xatolik: Matnni olib bo'lmadi.")

@dp.message(Command("thumb"))
async def get_thumb_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Format: /thumb <link>")
    url = parts[1].strip()
    status_msg = await message.reply("🖼 Muqova qidirilmoqda...")
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_video_info, url)
        thumb = info.get('thumbnail')
        if thumb:
            await message.reply_photo(photo=thumb)
            await status_msg.delete()
        else:
            await status_msg.edit_text("Muqova topilmadi.")
    except Exception:
        await status_msg.edit_text("Xatolik: Rasmni yuklab bo'lmadi.")

# ---------------------------------------------------------
# 7. ASOSIY QADAM: Link yuborilganda videoni tashlash
# ---------------------------------------------------------
@dp.message(F.text.regexp(r'https?://(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be)/.+'))
async def download_normal_video(message: Message):
    url = message.text.strip()
    status_msg = await message.reply("⚡ Video yuklanmoqda...")
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_video_info, url)
        direct_url = info.get('url')
        if direct_url:
            await message.reply_video(
                video=direct_url,
                caption="💡 <i>Ushbu videoga Reply qilib <b>/round</b>, <b>/audio</b> yoki <b>/cut 00:00 00:10</b> yuborishingiz mumkin!</i>",
                parse_mode="HTML"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("Videoni tortib bo'lmadi.")
    except Exception:
        await status_msg.edit_text("Xatolik: video yopiq profildan yoki havola noto'g'ri.")

# ---------------------------------------------------------
# 8. Web-server
# ---------------------------------------------------------
async def health_check(request):
    return web.Response(text="FlashFeatures Bot ishlamoqda!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    print("FlashFeatures Bot yangilanishi bilan ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())