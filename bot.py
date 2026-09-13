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

ydl_info_opts = {
    'quiet': True,
    'no_warnings': True,
    'format': 'best',
}

def get_media_info(url: str):
    with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
        return ydl.extract_info(url, download=False)

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
# PINTEREST UCHUN MAXSUS API (Rasm va Videolarni xatosiz olish)
# ---------------------------------------------------------
async def get_pinterest_media(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            real_url = url
            # 1. pin.it qisqa linkini to'liq URL'ga aylantirish
            if "pin.it" in url:
                async with session.get(url, allow_redirects=True) as resp:
                    real_url = str(resp.url)
            
            # 2. Pin ID raqamini ajratib olish
            pin_id_match = re.search(r'/pin/(\d+)', real_url)
            if not pin_id_match:
                return None, None
                
            pin_id = pin_id_match.group(1)
            
            # 3. Pinterest rasmiy ochiq widget API orqali ma'lumot olish
            api_url = f"https://widgets.pinterest.com/v3/pidgets/pins/info/?pin_ids={pin_id}"
            async with session.get(api_url) as resp:
                data = await resp.json()
                pin_data = data.get("data", {}).get("pins", {}).get(pin_id)
                if not pin_data:
                    return None, None
                
                # Agar video bo'lsa
                if pin_data.get("videos"):
                    return "video", real_url
                
                # Agar rasm bo'lsa (eng yuqori original sifatni oladi)
                images = pin_data.get("images", {})
                img_url = (
                    images.get("orig", {}).get("url") or 
                    images.get("736x", {}).get("url") or 
                    images.get("564x", {}).get("url") or 
                    images.get("236x", {}).get("url")
                )
                return "image", img_url
    except Exception:
        return None, None

# ---------------------------------------------------------
# 1. START
# ---------------------------------------------------------
@dp.message(CommandStart())
async def start_cmd(message: Message):
    await message.reply(
        "⚡️ <b>FlashFeatured Bot</b>'ga xush kelibsiz!\n\n"
        "Menga <b>Instagram, TikTok, YouTube</b> yoki <b>Pinterest</b> havolasini yuboring. Media yuklangach, tagidagi qulay tugmalar orqali barcha amallarni bajarasiz!",
        parse_mode="HTML"
    )

# ---------------------------------------------------------
# 2. UNIVERSAL LINK ISHLOVCHI
# ---------------------------------------------------------
URL_PATTERN = r'https?://(?:www\.)?(?:instagram\.com|youtube\.com|youtu\.be|tiktok\.com|vt\.tiktok\.com|pin\.it|pinterest\.com)/.+'

@dp.message(F.text.regexp(URL_PATTERN))
async def download_media(message: Message):
    raw_url = message.text.strip()
    status_msg = await message.reply("⚡ Media tayyorlanmoqda...")

    try:
        loop = asyncio.get_running_loop()

        # 1. Pinterest havolasi bo'lsa
        if "pin.it" in raw_url or "pinterest.com" in raw_url:
            m_type, res = await get_pinterest_media(raw_url)
            
            if m_type == "image" and res:
                await message.reply_photo(
                    photo=res,
                    caption="⚡ <b>FlashFeatured</b>\n🖼 Pinterest rasmi yuklandi!",
                    parse_mode="HTML"
                )
                return await status_msg.delete()
            elif m_type == "video" and res:
                raw_url = res  # Video linkini olib, pastdagi yt-dlp ga uzatamiz
            else:
                return await status_msg.edit_text("Pinterest ma'lumotlarini olib bo'lmadi.")

        # 2. Video format (Instagram, YouTube, TikTok, Pinterest Video)
        info = await loop.run_in_executor(None, get_media_info, raw_url)
        direct_url = info.get('url')

        if direct_url:
            await message.reply_video(
                video=direct_url,
                caption=f"⚡ <b>FlashFeatured</b>\nKerakli amalni tanlang:\n\n<code>{raw_url}</code>",
                reply_markup=get_action_keyboard(),
                parse_mode="HTML"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("Medianing to'g'ridan-to'g'ri havolasini olib bo'lmadi.")
            
    except Exception as e:
        await status_msg.edit_text("Xatolik: havola yopiq yoki noto'g'ri formatda.")

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
# 4. TUGMALAR ISHLOVCHILARI (TEZLIK OPTIMIZATSIYASI BILAN)
# ---------------------------------------------------------

# 4.1. AYLANa VIDEO (SCALE 240 + ULTRAFAST — ENG YUQORI TEZLIK)
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
            'ffmpeg', '-y',
            '-i', raw_video,
            '-t', '60',
            '-vf', "crop='min(iw,ih)':'min(iw,ih)',scale=240:240",
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '28',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-threads', '0',
            round_video
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        if os.path.exists(round_video):
            await callback.message.reply_video_note(video_note=FSInputFile(round_video))
        else:
            await callback.message.reply("Aylana video yasashda xatolik yuz berdi.")
    except Exception as e:
        await callback.message.reply(f"Xatolik: {e}")
    finally:
        for f in [raw_video, round_video]:
            if os.path.exists(f):
                os.remove(f)

# 4.2. MP3 AUDIO AJRATISH
@dp.callback_query(F.data == "audio_btn")
async def process_audio(callback: CallbackQuery):
    await callback.answer("Audio ajratilmoqda...")
    uid = callback.from_user.id
    raw_video = f"raw_audio_{uid}.mp4"
    audio_file = f"audio_{uid}.mp3"

    try:
        success = await fetch_target_video(callback, raw_video)
        if not success:
            return await callback.message.reply("Video topilmadi.")

        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-i', raw_video,
            '-vn',
            '-c:a', 'libmp3lame',
            '-q:a', '4',
            '-threads', '0',
            audio_file
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        if os.path.exists(audio_file):
            await callback.message.reply_audio(audio=FSInputFile(audio_file))
        else:
            await callback.message.reply("Audioni ajratib bo'lmadi.")
    except Exception as e:
        await callback.message.reply(f"Xatolik: {e}")
    finally:
        for f in [raw_video, audio_file]:
            if os.path.exists(f):
                os.remove(f)

# 4.3. QIRQISH (CUT) — FAST SEEK
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
            'ffmpeg', '-y',
            '-ss', start_time,
            '-to', end_time,
            '-i', raw_video,
            '-c', 'copy',
            cut_video
        ]
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: subprocess.run(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        if os.path.exists(cut_video):
            await message.reply_video(video=FSInputFile(cut_video))
            await status_msg.delete()
        else:
            await status_msg.edit_text("Videoni kesib bo'lmadi. Vaqt oralig'ini tekshiring.")
    except Exception as e:
        await status_msg.edit_text(f"Xatolik: {e}")
    finally:
        for f in [raw_video, cut_video]:
            if os.path.exists(f):
                os.remove(f)

# 4.4. TAVSIF / MATN
@dp.callback_query(F.data == "text_btn")
async def process_text(callback: CallbackQuery):
    await callback.answer("Tavsif olinmoqda...")
    caption = callback.message.caption or ""
    urls = [line.strip() for line in caption.split("\n") if line.strip().startswith("http")]
    
    if not urls:
        return await callback.message.reply("Video havolasi topilmadi.")

    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_media_info, urls[0])
        desc = info.get("description", "Tavsif mavjud emas.")
        await callback.message.reply(desc[:4000])
    except Exception:
        await callback.message.reply("Tavsifni olib bo'lmadi.")

# 4.5. MUQOVA (THUMBNAIL)
@dp.callback_query(F.data == "thumb_btn")
async def process_thumb(callback: CallbackQuery):
    await callback.answer("Muqova olinmoqda...")
    caption = callback.message.caption or ""
    urls = [line.strip() for line in caption.split("\n") if line.strip().startswith("http")]

    if not urls:
        return await callback.message.reply("Video havolasi topilmadi.")

    try:
        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, get_media_info, urls[0])
        thumb = info.get("thumbnail")
        if thumb:
            await callback.message.reply_photo(photo=thumb)
        else:
            await callback.message.reply("Muqova topilmadi.")
    except Exception:
        await callback.message.reply("Muqovani yuklab bo'lmadi.")

# ---------------------------------------------------------
# 5. UPTIMEROBOT UCHUN WEB-SERVER
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
    print("FlashFeatured Bot to'liq platformalar bilan ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())