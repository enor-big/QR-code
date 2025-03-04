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
TOKEN = "Добавьте ваш token"

# API Keys
API_URL = "https://api-key.fusionbrain.ai/"
API_KEY = "Добавьте ваш API_KEY"
SECRET_KEY = "Добавьте ваш secret_key"

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
def overlay_qr_on_image(background, qr_code, full_image=False, alpha=160):
    if full_image:
        # Если QR-код должен занять всю картинку
        qr_full = qr_code.resize(background.size, Image.LANCZOS)
        qr_full.putalpha(alpha)  # Установка прозрачности
        return Image.alpha_composite(background.convert("RGBA"), qr_full)
    else:
        # Если QR-код должен быть водяным знаком
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
        # Преобразуем данные в JSON-строку перед сохранением
        self.history[str(user_id)] = json.dumps(data, ensure_ascii=False)

    def get_last_request(self, user_id):
        # Извлекаем JSON-строку и преобразуем её обратно в словарь
        data_str = self.history.get(str(user_id))
        return json.loads(data_str) if data_str else None

user_history = UserHistory()

# FSM (машина состояний)
class Form(StatesGroup):
    qr_link = State()
    qr_type = State()  # Новое состояние для выбора типа QR-кода
    prompt = State()
    style = State()
    transparency = State()  # Новое состояние для выбора прозрачности

# Клавиатура выбора типа QR-кода
def qr_type_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📝 QR-код как водяной знак", callback_data="qr_watermark")],
        [InlineKeyboardButton(text="🖼️ QR-код на всю картинку", callback_data="qr_full_image")]
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

# Клавиатура для повторной генерации
def regenerate_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🔄 Повторить с теми же параметрами", callback_data="regenerate")],
        [InlineKeyboardButton(text="📝 Изменить параметры", callback_data="change_parameters")]
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
    await state.set_state(Form.qr_type)
    await message.answer("Выберите, как должен быть размещен QR-код:", reply_markup=qr_type_keyboard())

# Обработка выбора типа QR-кода
@router.callback_query(lambda c: c.data in ["qr_watermark", "qr_full_image"])
async def handle_qr_type(callback: types.CallbackQuery, state: FSMContext):
    qr_type_mapping = {
        "qr_watermark": False,
        "qr_full_image": True
    }
    selected_qr_type = qr_type_mapping.get(callback.data, False)
    await state.update_data(qr_type=selected_qr_type)
    await state.set_state(Form.prompt)
    await callback.message.answer("✅ Тип QR-кода выбран. Выберите тип промта:", reply_markup=prompt_choice_keyboard())
    await callback.answer()

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
# Словарь для отслеживания обработанных callback'ов
processed_callbacks = {}


@router.callback_query(lambda c: c.data.startswith("transparency_"))
async def handle_transparency(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Проверяем, был ли уже дан ответ на этот callback
        if callback.id in processed_callbacks:
            logger.info(f"Callback с ID {callback.id} уже был обработан.")
            return

        # Отмечаем callback как обработанный
        processed_callbacks[callback.id] = time.time()

        transparency_mapping = {
            "transparency_160": 160,
            "transparency_255": 255
        }
        selected_transparency = transparency_mapping.get(callback.data, 160)
        await state.update_data(transparency=selected_transparency)

        # Ответ на callback
        await callback.answer(f"✅ Выбран уровень прозрачности: {selected_transparency}")

        # Начинаем генерацию изображения
        await generate_image(callback.message, state)

    except aiogram.exceptions.TelegramBadRequest as e:
        logger.error(f"Ошибка при ответе на callback: {e}")
        await callback.message.answer("❌ Произошла ошибка. Попробуйте снова.")

# Генерация изображения
async def generate_image(message: Message, state: FSMContext):
    data = await state.get_data()
    qr_link = data.get("qr_link")
    prompt = data.get("prompt")
    style = data.get("style")
    qr_type = data.get("qr_type", False)  # По умолчанию QR-код как watermark
    transparency = data.get("transparency", 160)  # По умолчанию прозрачность 160

    if not (qr_link and prompt and style and transparency is not None):
        logger.error(f"Недостаточно данных для генерации: {data}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")
        await state.clear()
        return

    # Отправляем временное сообщение пользователю
    temporary_message = await message.answer("⏳ Идет генерация изображения... Это может занять некоторое время.")

    try:
        api = Text2ImageAPI()
        model_id = api.get_model()
        if model_id is None:
            await message.answer("❌ Ошибка: не удалось получить модель для генерации.")
            await state.clear()
            return

        uuid = api.generate(prompt, model_id, style)
        if uuid is None:
            await message.answer("❌ Ошибка генерации.")
            await state.clear()
            return

        images = api.check_generation(uuid)
        if not images:
            await message.answer("❌ Не удалось сгенерировать изображение.")
            await state.clear()
            return

        # Обработка изображения
        background_img = api.decode_image(images[0])
        qr_code_img = generate_qr_code(qr_link)
        final_img = overlay_qr_on_image(background_img, qr_code_img, full_image=qr_type, alpha=transparency)

        # Сохраняем результат
        file_path = f"final_result_{message.from_user.id}.png"
        final_img.save(file_path)

        # Сохраняем текущий запрос в историю
        user_history.save_request(message.from_user.id, data)

        # Удаляем временное сообщение
        await temporary_message.delete()

        # Отправляем результат пользователю
        await message.answer_photo(types.FSInputFile(file_path), caption="✅ Ваше изображение готово!")
        await message.answer("Что хотите сделать дальше?", reply_markup=regenerate_keyboard())

    except Exception as e:
        logger.error(f"Ошибка при генерации изображения: {e}")
        await message.answer("❌ Произошла ошибка при генерации изображения. Попробуйте снова.")

    finally:
        # Очищаем состояние FSM
        await state.clear()

# Обработка кнопки "Повторить с теми же параметрами"
@router.callback_query(lambda c: c.data == "regenerate")
async def regenerate_image(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Проверяем, был ли уже дан ответ на этот callback
        if processed_callbacks.get(callback.id):
            logger.info(f"Callback с ID {callback.id} уже был обработан.")
            return

            # Отмечаем callback как обработанный
        processed_callbacks[callback.id] = True

        # Отправляем уведомление через новое сообщение
        await callback.message.answer("🚀 Начинаем повторную генерацию...")

        user_id = callback.from_user.id
        last_request_str = user_history.get_last_request(user_id)

        if not last_request_str or not all(
            key in last_request_str for key in ["qr_link", "prompt", "style", "qr_type", "transparency"]
        ):
            logger.error(f"Для пользователя {user_id} история запросов пуста или недостаточно данных.")
            await callback.message.answer("❌ История запросов пуста. Сначала создайте изображение.")
            return

        logger.info(f"Восстановлены данные из истории для пользователя {user_id}: {last_request_str}")

        # Обновляем состояние FSM данными из последнего запроса
        await state.update_data(last_request_str)

        # Запускаем процесс генерации изображения
        await generate_image(callback.message, state)

    except aiogram.exceptions.TelegramBadRequest as e:
        if "query is too old" in str(e):
            await callback.message.answer("⚠️ Этот запрос устарел. Пожалуйста, повторите действие.")
        else:
            logger.error(f"Ошибка при ответе на callback: {e}")
            await callback.message.answer("❌ Произошла ошибка. Попробуйте снова.")

# Обработка кнопки "Изменить параметры"
@router.callback_query(lambda c: c.data == "change_parameters")
async def change_parameters(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.qr_link)
    await callback.message.answer("Отправьте новую ссылку для QR-кода или введите /start для начала заново.")
    await callback.answer()
# Запуск бота
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
