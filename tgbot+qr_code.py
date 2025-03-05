import json
import time
import requests
import base64
from io import BytesIO
from PIL import Image
import qrcode
import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import random
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot Token
TOKEN = "8035098218:AAFk4b8XB_n2ghEUzUsQjl_MgWOf6APug0E"

# API Keys
API_URL = "https://api-key.fusionbrain.ai/"
API_KEY = "6AAC667DF487820133143F17037CBB54"
SECRET_KEY = "7E55DE7139607DED7C9CB8FF604A3D25"

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Список случайных промтов на русском языке
RANDOM_PROMPTS = [
    "Закат над горным хребтом",
    "Будущий ночной город с летающими машинами",
    "Подводный мир с кораллами и разноцветными рыбами",
    "Магический лес с светящимися грибами",
    "Портрет человека в стиле киберпанк",
    "Дракон парит над средневековым замком",
    "Тихий пляж с пальмами и кристально чистой водой",
    "Стимпанк-инженерная конструкция",
    "Яркая абстрактная живопись с вихрями цветов",
    "Апокалиптический пейзаж после глобальной катастрофы",
    "Звездное небо над бескрайней пустыней",
    "Город будущего с голографическими рекламами",
    "Северное сияние над тайгой",
    "Космический корабль у планетарной системы",
    "Разноцветные поля цветов в солнечный день",
    "Мистический остров с древними руинами",
    "Ночной рынок в азиатском городе",
    "Фантастический город в облаках",
    "Морской бой между кораблями с драконами",
    "Таинственный портал в другое измерение",
    "Средневековый рыцарь на поле боя",
    "Космический ландшафт с несколькими солнцами",
    "Город под водой с коралловыми домами",
    "Волшебный рассвет над озером",
    "Античный храм среди зеленых холмов",
    "Лесные эльфы в свете луны",
    "Космическая станция над голубой планетой"
]

# Класс API для генерации изображений
class Text2ImageAPI:
    def __init__(self):
        self.URL = API_URL
        self.API_KEY = API_KEY
        self.SECRET_KEY = SECRET_KEY
        self.AUTH_HEADERS = {
            "X-Key": f"Key {self.API_KEY}",
            "X-Secret": f"Secret {self.SECRET_KEY}",
        }

    def get_model(self):
        """Получение ID модели."""
        response = requests.get(self.URL + "key/api/v1/models", headers=self.AUTH_HEADERS)
        if response.status_code == 200:
            data = response.json()
            return data[0]["id"] if data else None
        logger.error(f"Ошибка при получении модели: {response.status_code} - {response.text}")
        return None

    def generate(self, prompt, model, style, images=1, width=1024, height=1024):
        """Генерация изображения по тексту с учетом стиля."""
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {"query": f"{prompt}, style: {style}"}
        }
        data = {
            "model_id": (None, model),
            "params": (None, json.dumps(params, ensure_ascii=False), "application/json")
        }
        response = requests.post(self.URL + "key/api/v1/text2image/run", headers=self.AUTH_HEADERS, files=data)
        if response.status_code == 201:
            return response.json().get("uuid")
        logger.error(f"Ошибка генерации изображения: {response.status_code} - {response.text}")
        return None

    def check_generation(self, request_id, attempts=20, delay=10):
        """Ожидание завершения генерации."""
        while attempts > 0:
            response = requests.get(self.URL + f"key/api/v1/text2image/status/{request_id}", headers=self.AUTH_HEADERS)
            data = response.json()
            if data.get("status") == "DONE":
                return data.get("images", [])
            logger.info(f"Проверка статуса генерации ({attempts} попыток осталось)")
            time.sleep(delay)
            attempts -= 1
        logger.error(f"Не удалось завершить генерацию")
        return []

    @staticmethod
    def decode_image(base64_string):
        """Декодирование base64-изображения."""
        image_data = base64.b64decode(base64_string)
        return Image.open(BytesIO(image_data))

# Функция создания QR-кода без закругленных углов
def generate_qr_code(data, size=300):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill="black", back_color="white").convert("RGBA")
    qr_img = qr_img.resize((size, size), Image.LANCZOS)
    return qr_img

# Функция наложения QR-кода на изображение
def overlay_qr_on_image(background, qr_code, alpha=160):
    bg_width, bg_height = background.size
    qr_width, qr_height = qr_code.size
    qr_overlay = qr_code.copy()
    qr_overlay.putalpha(alpha)  # Уровень прозрачности
    position = ((bg_width - qr_width) // 2, (bg_height - qr_height) // 2)
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    overlay.paste(qr_overlay, position, qr_overlay)
    return Image.alpha_composite(background.convert("RGBA"), overlay)

# Хранение истории запросов
class UserHistory:
    def __init__(self):
        self.history = {}

    def save_request(self, user_id, data):
        self.history[str(user_id)] = json.dumps(data, ensure_ascii=False)

    def get_last_request(self, user_id):
        data_str = self.history.get(str(user_id))
        return json.loads(data_str) if data_str else None

user_history = UserHistory()

# FSM (машина состояний)
class Form(StatesGroup):
    qr_link = State()
    prompt = State()
    style = State()
    transparency = State()

# Клавиатура выбора типа QR-кода
def qr_type_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📝 QR-код как водяной знак", callback_data="qr_watermark")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура выбора стиля
def style_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🎨 Реализм", callback_data="style_realism")],
        [InlineKeyboardButton(text="🖌 Арт", callback_data="style_art")],
        [InlineKeyboardButton(text="🌌 Фантастика", callback_data="style_fantasy")],
        [InlineKeyboardButton(text="👾 Киберпанк", callback_data="style_cyberpunk")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для выбора типа промта
def prompt_choice_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📝 Ввести свой промт", callback_data="custom_prompt")],
        [InlineKeyboardButton(text="🎲 Использовать случайный промт", callback_data="random_prompt")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для выбора прозрачности
def transparency_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📊 Средняя прозрачность (160)", callback_data="transparency_160")],
        [InlineKeyboardButton(text="⬛ Без прозрачности (255)", callback_data="transparency_255")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Клавиатура для продолжения
def continue_keyboard():
    buttons = [
        [InlineKeyboardButton(text="✅ Да", callback_data="continue_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="continue_no")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Команда /start
@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.set_state(Form.qr_link)
    await message.answer("👋 Привет! Отправьте ссылку для QR-кода.")

# Приём ссылки и предложение выбора типа QR-кода
@router.message(Form.qr_link)
async def get_qr_link(message: Message, state: FSMContext):
    if not message.text.startswith("http"):
        await message.answer("❌ Пожалуйста, отправьте корректную ссылку.")
        return

    await state.update_data(qr_link=message.text.strip())
    await state.set_state(Form.prompt)
    await message.answer("✅ Тип QR-кода выбран. Выберите тип промта:", reply_markup=prompt_choice_keyboard())

# Обработка выбора типа промта
@router.callback_query(lambda c: c.data in ["custom_prompt", "random_prompt"])
async def handle_prompt_choice(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "custom_prompt":
        await callback.message.answer("Введите ваш промт:")
    elif callback.data == "random_prompt":
        random_prompt = random.choice(RANDOM_PROMPTS)
        await state.update_data(prompt=random_prompt)
        await callback.message.answer(f"Используется случайный промт: {random_prompt}")
        await state.set_state(Form.style)
        await callback.message.answer("🎨 Выберите стиль генерации:", reply_markup=style_keyboard())
    await callback.answer()

# Приём пользовательского промта
@router.message(Form.prompt)
async def get_custom_prompt(message: Message, state: FSMContext):
    await state.update_data(prompt=message.text.strip())
    await state.set_state(Form.style)
    await message.answer("🎨 Выберите стиль генерации:", reply_markup=style_keyboard())

# Обработка выбора стиля
@router.callback_query(lambda c: c.data.startswith("style_"))
async def select_style(callback: types.CallbackQuery, state: FSMContext):
    style_mapping = {
        "style_realism": "Realism",
        "style_art": "Artistic",
        "style_fantasy": "Fantasy",
        "style_cyberpunk": "Cyberpunk"
    }
    selected_style = style_mapping.get(callback.data, "Realism")
    await state.update_data(style=selected_style)
    await state.set_state(Form.transparency)
    await callback.message.answer(f"✅ Выбран стиль: {selected_style}\nВыберите уровень прозрачности QR-кода:", reply_markup=transparency_keyboard())
    await callback.answer()

# Обработка выбора прозрачности
@router.callback_query(lambda c: c.data.startswith("transparency_"))
async def handle_transparency(callback: types.CallbackQuery, state: FSMContext):
    transparency_mapping = {
        "transparency_160": 160,
        "transparency_255": 255
    }
    selected_transparency = transparency_mapping.get(callback.data, 160)
    await state.update_data(transparency=selected_transparency)
    await callback.answer(f"✅ Выбран уровень прозрачности: {selected_transparency}")
    await generate_image(callback.message, state)

# Генерация изображения
async def generate_image(message: Message, state: FSMContext):
    data = await state.get_data()
    qr_link = data.get("qr_link")
    prompt = data.get("prompt")
    style = data.get("style")
    transparency = data.get("transparency", 160)

    if not (qr_link and prompt and style and transparency is not None):
        logger.error(f"Недостаточно данных для генерации: {data}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
        return

    temporary_message = await message.answer("⏳ Идет генерация изображения... Это может занять некоторое время.")

    try:
        api = Text2ImageAPI()
        model_id = api.get_model()
        if model_id is None:
            await message.answer("❌ Ошибка: не удалось получить модель для генерации.")
            return

        uuid = api.generate(prompt, model_id, style)
        if uuid is None:
            await message.answer("❌ Ошибка генерации.")
            return

        images = api.check_generation(uuid)
        if not images:
            await message.answer("❌ Не удалось сгенерировать изображение.")
            return

        background_img = api.decode_image(images[0])
        qr_code_img = generate_qr_code(qr_link)
        final_img = overlay_qr_on_image(background_img, qr_code_img, alpha=transparency)

        file_path = f"final_result_{message.from_user.id}.png"
        final_img.save(file_path)

        user_history.save_request(message.from_user.id, data)
        logger.info(f"Сохранены данные для пользователя {message.from_user.id}: {data}")

        await temporary_message.delete()
        await message.answer_photo(types.FSInputFile(file_path), caption="✅ Ваше изображение готово!")
        await message.answer("Желаете продолжить?", reply_markup=continue_keyboard())

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        await message.answer("❌ Произошла ошибка при генерации изображения. Попробуйте снова.")

    finally:
        await state.clear()

# Обработка кнопки "Продолжить"
@router.callback_query(lambda c: c.data == "continue_yes")
async def continue_process(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.qr_link)
    await callback.message.answer("Отлично! Отправьте новую ссылку для QR-кода или введите /start для начала заново.")
    await callback.answer()

# Обработка кнопки "Завершить"
@router.callback_query(lambda c: c.data == "continue_no")
async def stop_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("До встречи! Если захотите продолжить, просто отправьте /start.")
    await callback.answer()

# Запуск бота
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
