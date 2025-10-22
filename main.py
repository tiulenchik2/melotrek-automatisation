"""
By @mmetalboy
Помощь Колі з автоматизацією мелотреку
<3
"""
import gspread
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, ContentType
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from typing import Dict, Tuple, List
from collections import defaultdict
import aiosqlite
from dotenv import load_dotenv
from os import getenv, mkdir, listdir
from os.path import isdir, splitext

load_dotenv()
bot = Bot(token=getenv("BOT_TOKEN"))
pathdb = "database.db"
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
album_cache: Dict[Tuple[int, str], List[Message]] = defaultdict(list)

gc = gspread.service_account(filename="melotrek-bot.json")

class Init(StatesGroup):
    init_table = State()
    show_names = State()
    choose_cap_for_photo = State()
    send_photos = State()

async def init_db():
    try:
        async with aiosqlite.connect(pathdb) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS Captions(ColumnLetter TEXT PRIMARY KEY NOT NULL, Caption TEXT NOT NULL);")
            await db.execute("CREATE TABLE IF NOT EXISTS Names(Id INTEGER PRIMARY KEY AUTOINCREMENT, ColumnLetter TEXT NOT NULL, Name TEXT NOT NULL);")
            await db.commit()
    except Exception as e:
        print(f"База даних не ініціалізована: {str(e)}")
    else:
        print("База даних в порядку.")
        
async def insert_data(sheet):
    captions = []
    for a in [chr(x) for x in range (66, 91)]:
        cell_name = f"{a}2"
        cell_value = sheet.acell(cell_name).value
        pair = (str(a), str(cell_value))
        if cell_value != None: captions.append(pair)
    names = sheet.get_values("B28:Q35")
    letters = [chr(x) for x in range(66,82)]
    for b in range(len(names)):
        for a in range(len(names[b])):
            names[b][a] = (letters[a], names[b][a].replace("\r", "").replace("\n", ""))
    try:
        async with aiosqlite.connect(pathdb) as db:
            await db.executemany("INSERT OR REPLACE INTO Captions (ColumnLetter, Caption) VALUES (?,?)", captions)
            for name in names:
                await db.executemany("INSERT OR REPLACE INTO Names (ColumnLetter, Name) VALUES (?,?)", name)
            await db.commit()
    except Exception as e:
        print(f"Не вдалось вставити дані: {str(e)}")
    else:
        print("Дані вставлено.")

async def get_caps_in_single_list():
    async with aiosqlite.connect(pathdb) as db:
        caps = await db.execute_fetchall("SELECT * FROM Captions")
        if not caps:
            return None
        caps = [caps[x][1] for x in range(len(caps))]
        return caps
    
async def get_names_in_single_list(caption):
    async with aiosqlite.connect(pathdb) as db:
        names = await db.execute_fetchall("""
            SELECT T1.Name, T1.ColumnLetter FROM Names AS T1 INNER JOIN Captions AS T2 ON
            T1.ColumnLetter = T2.ColumnLetter WHERE T2.Caption LIKE ?;
            """, (f"{caption}%",))
        names = [names[x][0] for x in range(len(names))]
    return names

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Hello World!")

@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == None: 
        await message.answer("Нічого відміняти.")
        return
    await state.clear()
    await message.answer("Дія відмінена.", reply_markup=ReplyKeyboardRemove())

@dp.message(Command("init_table"), StateFilter(None))
async def ask_init_table(message: Message, state: FSMContext):
    await message.answer("Виконуйте ініціалізацію лише на початку користування! (або коли змінився лінк...)\nНадішліть лінк на таблицю у Гугл Таблицях.\n\nВідміна дії - /cancel")
    await state.set_state(Init.init_table)

@dp.message(Command("get_caps"))
async def get_caps_command(message: Message):
    caps = await get_caps_in_single_list()
    if caps == None:
        await message.reply("Пусто! Можливо, потрібно ініціалізувати таблицю! /init_table")
        return
    message_caps = "\n".join(caps)
    await message.reply(message_caps)

@dp.message(Command("get_names"))
async def get_names_command(message: Message, state: FSMContext):
    caps = await get_caps_in_single_list()
    if caps == None:
        await message.reply("Пусто! Можливо, потрібно ініціалізувати таблицю! /init_table")
        return
    caps_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in caps]])
    await message.reply("Оберіть категорію.", reply_markup=caps_kb)
    await state.set_state(Init.show_names)

@dp.message(Init.show_names)
async def show_names_text(message: Message, state: FSMContext):
    await state.update_data(cap=message.text)
    cap_show = (await state.get_data())["cap"]
    try:
        names = await get_names_in_single_list(cap_show)
        print(names)
        message_names = "\n".join(names)
        await message.reply(message_names)
    except Exception as e:
        await message.reply(f"Помилка! {str(e)}")

@dp.message(Init.init_table)
async def init_table(message: Message, state: FSMContext):
    await state.update_data(table=message.text)
    table_link = (await state.get_data())["table"]
    await message.answer("Бот не завис. Обробляю таблицю...")
    try:
        sheet = gc.open_by_url(table_link).sheet1
    except Exception as e:
        await message.answer(f"Виникла помилка.\n\n{str(e)}")
    else:
        await insert_data(sheet)
    await message.reply("Таблицю ініціалізовано. Для перевірки правильності даних можете прописати /get_caps для назв категорії або /get_names для назв треків певної категорії.")
    await state.clear()

@dp.message(Command("send_photos"))
async def start_sending_nudes(message: Message, state: FSMContext):
    await state.set_state(Init.choose_cap_for_photo)
    caps = await get_caps_in_single_list()
    if caps == None:
        await message.reply("Пусто! Можливо, потрібно ініціалізувати таблицю! /init_table")
        return
    caps_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=x) for x in caps]])
    await message.reply("Оберіть категорію, для якої потрібно зробити фоточки.", reply_markup=caps_kb)

async def is_valid_category(message: Message) -> bool:
    """Перевіряє, чи текст повідомлення є дійсним заголовком категорії."""
    caps = await get_caps_in_single_list() 
    
    return message.text in caps

@dp.message(Init.choose_cap_for_photo, is_valid_category)
async def continue_sending(message: Message, state: FSMContext):
    await state.update_data(cap=message.text)
    cap_photo = (await state.get_data())["cap"]
    dir_cap = str(cap_photo).replace(" ", "_")
    if isdir(f"photos/{dir_cap}") and listdir(f"photos/{dir_cap}"):
        await message.reply("Для цієї категорії вже є фотки.")
        return
    if not isdir(f"photos/{dir_cap}"): mkdir(f"photos/{dir_cap}")
    names = await get_names_in_single_list(cap_photo)
    message_names = "\n".join(names)
    await state.update_data(expected_count=len(names))
    await message.reply(f"Обрано категорію {cap_photo}.\nНадішліть {len(names)} обкладинок у такому порядку:\n {message_names}")
    await state.update_data(dir_cap=dir_cap)
    await state.set_state(Init.send_photos)

async def process_complete_album(chat_id: int, group_id: str, state: FSMContext):
    state_data = await state.get_data()
    cache_key = (chat_id, group_id)
    dir_cap = state_data["dir_cap"]
    album: List[Message] = album_cache.pop(cache_key) 
    actual_count = len(album)
    album.sort(key=lambda msg: msg.message_id)
    expected_count = state_data["expected_count"]
    if expected_count is None:
        return await bot.send_message(chat_id, "Помилка: Не вдалося визначити очікувану кількість.")
    if actual_count == expected_count:
        await bot.send_message(chat_id, f"Успіх! Надіслано рівно {expected_count} фотографій.")
        for i, message_part in enumerate(album):
            file_id = message_part.photo[-1].file_id
            file = await bot.get_file(file_id)
            file_extension = splitext(file.file_path)[1]
            await bot.download_file(file.file_path, f"photos/{dir_cap}/{i}{file_extension}")

            # РОБОТА З ВІДОСОМ ТУТ.
            # ЧИ ФУНКЦІЯ, ЧИ ЩО ТУТ В ТЕБЕ БЛЯТЬ.
    else:
        await bot.send_message(
            chat_id, 
            f"Помилка! Очікувалось {expected_count} фото, але надіслано {actual_count}. Спробуйте ще раз."
        )

@dp.message(Init.send_photos, F.content_type == ContentType.PHOTO, F.media_group_id)
async def get_photos(message: Message, state: FSMContext):
    cache_key = (message.chat.id, message.media_group_id)
    album_cache[cache_key].append(message)
    if len(album_cache[cache_key]) == 1:
        await asyncio.sleep(1) 
        await process_complete_album(message.chat.id, message.media_group_id, state)


async def main():
    if not isdir("photos"): mkdir("photos")
    await bot.delete_webhook(drop_pending_updates=True)
    await init_db()
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())