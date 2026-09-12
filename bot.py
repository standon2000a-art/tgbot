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

BOT_TOKEN = os.getenv("8644709664:AAE4ykG8Mg5GZu73XoW-quiZ72P_qlEXCHo", "8644709664:AAE4ykG8Mg5GZu73XoW-quiZ72P_qlEXCHo")

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

@dp.message(CommandStart())
async def start_cmd(message: Message):
    text = (
        "⚡️ <b>FlashFeatures Bot</b>'ga xush kelibsiz!\n\n"
        "Men universal media yordamchingizman:\n"
        "🔗 <b>[Link]</b> — Videoni yuklash\n"
        "🔄 <b>/round [Link]</b> — Aylana video yasash\n"
        "🎵 <b>/audio [Link]</b> — MP3 audioni ajratish\n"
        "✂️ <b>/cut 00:10 00:25 [Link]</b> — Videoni kesish\n"
        "🖼 <b>/thumb [Link]</b> — Video muqovasini olish\n"
        "📝 <b>/text [Link]</b> — Video tavsifini olish"
    )
    await message.reply(text, parse_mode="HTML")

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
            await status_msg.edit_text("Muqova rasmi topilmadi.")
    except Exception:
        await status_msg.edit_text("Xatolik: Rasmni yuklab bo'lmadi.")

@dp.message(Command("audio"))
async def get_audio_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Format: /audio <link>")
    url = parts[1].strip()
    status_msg = await message.reply("🎵 Audio ajratib olinmoqda...")
    uid = message.from_user.id
    audio_base = f"audio_{uid}"
    audio_file = f"{audio_base}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{audio_base}.%(ext)s",
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True,
    }
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        if os.path.exists(audio_file):
            await message.reply_audio(audio=FSInputFile(audio_file))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Audioni chiqarib bo'lmadi.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        if os.path.exists(audio_file):
            os.remove(audio_file)

@dp.message(Command("cut"))
async def cut_video_cmd(message: Message):
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        return await message.reply("Format: /cut 00:10 00:25 <link>")
    start_time, end_time, url = parts[1].strip(), parts[2].strip(), parts[3].strip()
    status_msg = await message.reply(f"✂️ Video {start_time} dan {end_time} gacha qirqilmoqda...")
    uid = message.from_user.id
    raw_video = f"raw_{uid}.mp4"
    cut_video = f"cut_{uid}.mp4"
    try:
        ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': raw_video, 'quiet': True}
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        
        ffmpeg_cmd = ['ffmpeg', '-y', '-ss', start_time, '-to', end_time, '-i', raw_video, '-c', 'copy', cut_video]
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        
        if os.path.exists(cut_video):
            await message.reply_video(video=FSInputFile(cut_video))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Videoni qirqib bo'lmadi.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        for f in [raw_video, cut_video]:
            if os.path.exists(f):
                os.remove(f)

@dp.message(Command("round"))
async def round_video_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Format: /round <link>")
    url = parts[1].strip()
    status_msg = await message.reply("🔄 Aylana video tayyorlanmoqda...")
    uid = message.from_user.id
    raw_video = f"raw_round_{uid}.mp4"
    round_video = f"round_{uid}.mp4"
    try:
        ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': raw_video, 'quiet': True}
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        
        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', raw_video, '-t', '60',
            '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=480:480",
            '-c:v', 'libx264', '-c:a', 'aac', round_video
        ]
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

@dp.message(F.text.regexp(r'https?://(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be)/.+'))
async def download_normal_video(message: Message):
    url = message.text.strip()
    status_msg = await message.reply("⚡ Video tayyorlanmoqda...")
    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_video_info, url)
        direct_url = info.get('url')
        if direct_url:
            await message.reply_video(video=direct_url)
            await status_msg.delete()
        else:
            await status_msg.edit_text("Videoni tortib bo'lmadi.")
    except Exception:
        await status_msg.edit_text("Xatolik yuz berdi yoki havola yopiq profildan.")

# UptimeRobot va Render uchun Web server
async def health_check(request):
    return web.Response(text="Bot faol ishlamoqda!")

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
    print("FlashFeatures Bot 24/7 rejimida ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())