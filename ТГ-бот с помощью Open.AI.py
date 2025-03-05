import os
import qrcode
import aiogram
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import openai
import requests
import asyncio

API_TOKEN = 'Ваш тг бот API'
OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'

default_bot_properties = aiogram.client.bot.DefaultBotProperties(parse_mode=ParseMode.HTML)

bot = Bot(token=API_TOKEN, default=default_bot_properties)
dp = Dispatcher()
openai.api_key = OPENAI_API_KEY

class Form(StatesGroup):
    waiting_for_url = State()
    waiting_for_parameters = State()

@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    await message.answer("Привет! Отправь мне ссылку, для которой нужно создать QR-код.")
    await state.set_state(Form.waiting_for_url)

@dp.message(Form.waiting_for_url)
async def process_url(message: types.Message, state: FSMContext):
    url = message.text
    if not url.startswith(('http://', 'https://')):
        await message.answer("Пожалуйста, отправьте корректную ссылку.")
        return
    await state.update_data(url=url)
    await message.answer("Молодец! Теперь отправьте параметры для QR-кода (например, цвет, размер, стиль).")
    await state.set_state(Form.waiting_for_parameters)

@dp.message(Form.waiting_for_parameters)
async def process_parameters(message: types.Message, state: FSMContext):
    parameters = message.text
    data = await state.get_data()
    url = data.get('url')

    gpt_response = await ask_gpt(f"Создай QR-код для ссылки {url} с параметрами: {parameters}. Какие настройки использовать?")
    await message.answer(f"Настройки для QR-кода: {gpt_response}")

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        fill_color = "black"
        back_color = "white"

        if "fill_color" in gpt_response:
            fill_color = gpt_response.split("fill_color=")[1].split()[0]
        if "back_color" in gpt_response:
            back_color = gpt_response.split("back_color=")[1].split()[0]

        img = qr.make_image(fill_color=fill_color, back_color=back_color)
        img.save("qrcode.png")

        await message.answer_photo(InputFile("qrcode.png"), caption="Вот ваш QR-код!")
    except Exception as e:
        await message.answer(f"Произошла ошибка при создании QR-кода: {e}")

    await state.clear()

async def ask_gpt(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты помогаешь создавать QR-коды. Выводи только настройки для создания QR-кода."},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": ""}
        ],
        max_tokens=100,
        n=1,
        stop=None,
        temperature=0.7,
    )
    return response.choices[0].message['content'].strip()

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
