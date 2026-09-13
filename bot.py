import static_ffmpeg
static_ffmpeg.add_paths()

import asyncio
import os
import re
import subprocess
import aiohttp
import yt_dlp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    FSInputFile,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Render Environment Variables bo'limiga BOT_TOKEN qo'shilganini tekshiring.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Video qirqish holati uchun FSM
class CutState(StatesGroup):
    waiting_for_time = State()

# Yt-dlp sozlamalari (Faqat to'g'ridan-to'g'ri mp4 videolarni olish uchun)
ydl_info_opts = {
    'quiet': True,
    'no_warnings': True,
    'format': 'best[ext=mp4]/best',
}

def get_action_keyboard() -> InlineKeyboardMarkup:
    """Video tagidagi boshqaruv paneli"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Aylana video", callback_data="round_btn"),
                InlineKeyboardButton(text="🎵 MP3 Audio", callback_data="audio_btn"),
            ],
            [
                InlineKeyboardButton(text="✂️ Qirqish (Cut)", callback_data="cut_btn"),
                InlineKeyboardButton(text="🖼 Muqova (Thumb)", callback_data="thumb_btn"),
            ],
            [
                InlineKeyboardButton(text="📝 Tavsif / Matn", callback_data="text_btn")
            ]
        ]
    )

# ---------------------------------------------------------
# 1. HAVOLALARNI VA MEDIANI ANIQLASH FUNKSIYALARI
# ---------------------------------------------------------

# Qisqa linklarni (pin.it, vt.tiktok) haqiqiy URL ga aylantirish
async def resolve_url(url: str) -> str:
    if "pin.it" not in url and "vt.tiktok" not in url:
        return url
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, allow_redirects=True, timeout=10) as resp:
                return str(resp.url)
    except Exception:
        return url

# Video ma'lumotlarini olish
def extract_video_sync(url: str):
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("No info extracted")
        
        # Agar bu playlist yoki carousel bo'lsa (Masalan IG Post), birinchisini olamiz
        if 'entries' in info and len(info['entries']) > 0:
            info = info['entries'][0]
            
        if not info.get('url'):
            raise ValueError("Video formati topilmadi")
            
        return info

# Agar video bo'lmasa, HTML ichidan to'g'ridan-to'g'ri rasmni qirqib olish (Zaxira tizimi)
async def fallback_image_scraper(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                html = await resp.text()
                # Rasm uchun meta tegini izlash
                match = re.search(r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if match:
                    img_url = match.group(1)
                    # Pinterest rasmlarini original (HD) sifatga ko'tarish
                    if "pinimg.com" in img_url:
                        img_url = img_url.replace('/236x/', '/736x/').replace('/474x/', '/736x/')
                    return img_url
    except Exception:
        pass
    return None


# ---------------------------------------------------------
# 2. BOT HANDLERLARI (ASOSIY ISH JARAYONI)
# ---------------------------------------------------------
@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.reply(
        "⚡️ <b>FlashFeatured Bot</b>'ga xush kelibsiz!\n\n"
        "Menga <b>Instagram, TikTok, YouTube</b> yoki <b>Pinterest</b> havolasini yuboring. Rasm bo'lsa rasm, video bo'lsa video qilib chiqarib beraman!",
        parse_mode="HTML"
    )

URL_PATTERN = r'https?://(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be|tiktok\.com|vt\.tiktok\.com|pin\.it|pinterest\.com)/.+'

@dp.message(F.text.regexp(URL_PATTERN))
async def download_media(message: Message):
    raw_url = message.text.strip()
    status_msg = await message.reply("⚡ Media tayyorlanmoqda...")

    try:
        # 1. Avval qisqa havolani to'liq havolaga o'giramiz
        resolved_url = await resolve_url(raw_url)
        loop = asyncio.get_running_loop()
        
        # 2. Eng avval videoga tekshiramiz (yt-dlp orqali)
        try:
            info = await loop.run_in_executor(None, extract_video_sync, resolved_url)
            direct_url = info.get('url')
            
            if direct_url:
                await message.reply_video(
                    video=direct_url,
                    caption=f"⚡ <b>FlashFeatured</b>\nKerakli amalni tanlang:\n\n<code>{raw_url}</code>",
                    reply_markup=get_action_keyboard(),
                    parse_mode="HTML"
                )
                return await status_msg.delete()
        except Exception:
            # yt-dlp xato bersa (demak bu video emas, rasm bo'lishi ehtimoli katta)
            pass 
            
        # 3. Agar video chiqmasa, Rasm sifatida tortib ko'ramiz
        img_url = await fallback_image_scraper(resolved_url)
        if img_url:
            await message.reply_photo(
                photo=img_url,
                caption=f"⚡ <b>FlashFeatured</b>\n🖼 Rasm yuklandi!\n\n<code>{raw_url}</code>",
                parse_mode="HTML"
            )
            return await status_msg.delete()
            
        # Ikkalasidan ham o'tolmasa
        await status_msg.edit_text("Xatolik: Media ma'lumotlarini olib bo'lmadi. Havola yopiq profildan bo'lishi mumkin.")

    except Exception as e:
        await status_msg.edit_text("Xatolik: Tarmoq yoki ulanishda xato yuz berdi.")

# ---------------------------------------------------------
# 3. YORDAMCHI: Video faylni Telegramdan yuklab olish
# ---------------------------------------------------------
async def fetch_target_video(callback: CallbackQuery, path: str):
    if callback.message and callback.message.video:
        file = await bot.get_file(callback.message.video.file_id)
        await bot.download_file(file.file_path, path)
        return True
    return False

# ---------------------------------------------------------
# 4. TUGMALAR ISHLOVCHILARI (ROUND, AUDIO, CUT, THUMB)
# ---------------------------------------------------------

@dp.callback_query(F.data == "round_btn")
async def process_round(callback: CallbackQuery):
    await callback.answer("Aylana video tayyorlanmoqda...")
    uid = callback.from_user.id
    raw_video = f"raw_round_{uid}.mp4"
    round_video = f"round_{uid}.mp4"

    try:
        success = await fetch_target_video(callback, raw_video)
        if not success:
            return await callback.message.reply("Video topilmadi.")

        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', raw_video, '-t', '60',
            '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=240:240",
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28',
            '-c:a', 'aac', '-b:a', '128k', '-threads', '0', round_video
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        if os.path.exists(round_video):
            await callback.message.reply_video_note(video_note=FSInputFile(round_video))
        else:
            await callback.message.reply("Aylana video yasashda xatolik yuz berdi.")
    except Exception as e:
        pass
    finally:
        for f in [raw_video, round_video]:
            if os.path.exists(f): os.remove(f)

@dp.callback_query(F.data == "audio_btn")
async def process_audio(callback: CallbackQuery):
    await callback.answer("Audio ajratilmoqda...")
    uid = callback.from_user.id
    raw_video = f"raw_audio_{uid}.mp4"
    audio_file = f"audio_{uid}.mp3"

    try:
        success = await fetch_target_video(callback, raw_video)
        if not success: return await callback.message.reply("Video topilmadi.")

        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', raw_video, '-vn',
            '-c:a', 'libmp3lame', '-q:a', '4', '-threads', '0', audio_file
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        if os.path.exists(audio_file):
            await callback.message.reply_audio(audio=FSInputFile(audio_file))
    except Exception:
        pass
    finally:
        for f in [raw_video, audio_file]:
            if os.path.exists(f): os.remove(f)

@dp.callback_query(F.data == "cut_btn")
async def ask_cut_time(callback: CallbackQuery, state: FSMContext):
    if not callback.message.video:
        return await callback.answer("Video topilmadi.")
    
    await state.update_data(video_file_id=callback.message.video.file_id)
    await state.set_state(CutState.waiting_for_time)
    await callback.answer()
    await callback.message.reply(
        "✂️ Qirqish vaqtini yuboring:\nFormat: <code>00:05 00:15</code> (boshlanish va tugash)",
        parse_mode="HTML"
    )

@dp.message(CutState.waiting_for_time)
async def process_cut_time(message: Message, state: FSMContext):
    times = message.text.strip().split()
    if len(times) != 2:
        return await message.reply("Noto'g'ri format! Masalan: <code>00:05 00:20</code>", parse_mode="HTML")

    start_time, end_time = times[0], times[1]
    status_msg = await message.reply(f"✂️ {start_time} dan {end_time} gacha kesilmoqda...")
    data = await state.get_data()
    file_id = data.get("video_file_id")
    await state.clear()

    uid = message.from_user.id
    raw_video = f"raw_cut_{uid}.mp4"
    cut_video = f"cut_{uid}.mp4"

    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, raw_video)

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
        pass
    finally:
        for f in [raw_video, cut_video]:
            if os.path.exists(f): os.remove(f)

@dp.callback_query(F.data == "text_btn")
async def process_text(callback: CallbackQuery):
    await callback.answer("Tavsif olinmoqda...")
    caption = callback.message.caption or ""
    urls = [line.strip() for line in caption.split("\n") if line.strip().startswith("http")]
    
    if not urls: return await callback.message.reply("Video havolasi topilmadi.")

    try:
        resolved = await resolve_url(urls[0])
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, extract_video_sync, resolved)
        desc = info.get("description", "Tavsif mavjud emas.")
        await callback.message.reply(desc[:4000])
    except Exception:
        await callback.message.reply("Tavsifni olib bo'lmadi.")

@dp.callback_query(F.data == "thumb_btn")
async def process_thumb(callback: CallbackQuery):
    await callback.answer("Muqova olinmoqda...")
    caption = callback.message.caption or ""
    urls = [line.strip() for line in caption.split("\n") if line.strip().startswith("http")]

    if not urls: return await callback.message.reply("Video havolasi topilmadi.")

    try:
        resolved = await resolve_url(urls[0])
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, extract_video_sync, resolved)
        thumb = info.get("thumbnail")
        if thumb:
            await callback.message.reply_photo(photo=thumb)
        else:
            await callback.message.reply("Muqova topilmadi.")
    except Exception:
        await callback.message.reply("Muqovani yuklab bo'lmadi.")

# ---------------------------------------------------------
# 5. UPTIMEROBOT WEB-SERVER (Render 24/7 ishlashi uchun)
# ---------------------------------------------------------
async def health_check(request):
    return web.Response(text="FlashFeatured Bot ishlamoqda!")

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
    print("FlashFeatured Bot to'liq tayyor...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())