import json
import time
import requests
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter
import qrcode


class Text2ImageAPI:
    def __init__(self, url, api_key, secret_key):
        """Инициализация API."""
        self.URL = url
        self.API_KEY = api_key
        self.SECRET_KEY = secret_key
        self.AUTH_HEADERS = {
            'X-Key': f'Key {self.API_KEY}',
            'X-Secret': f'Secret {self.SECRET_KEY}',
        }

    def get_model(self):
        """Получение модели для генерации изображений."""
        try:
            print("🔄 Получение модели...")
            response = requests.get(self.URL + 'key/api/v1/models', headers=self.AUTH_HEADERS)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"❌ Ошибка API ({response.status_code}): {response.text}")
                return None

            data = response.json()
            return data[0]['id'] if data else None

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к API: {e}")
            return None

    def generate(self, prompt, model, images=1, width=1024, height=1024):
        """Отправка запроса на генерацию изображения."""
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": prompt
            }
        }

        data = {
            'model_id': (None, model),
            'params': (None, json.dumps(params, ensure_ascii=False), 'application/json'),
        }

        try:
            print(f"🖼️ Генерация изображения по запросу: {prompt}")
            response = requests.post(self.URL + 'key/api/v1/text2image/run', headers=self.AUTH_HEADERS, files=data)
            response.encoding = 'utf-8'
            data = response.json()

            print(f"🔍 Ответ API ({response.status_code}): {data}")

            if response.status_code == 201 and "uuid" in data:
                return data['uuid']  # Генерация запущена, возвращаем UUID

            print(f"❌ Ошибка генерации: {response.status_code} - {data}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к API: {e}")
            return None

    def check_generation(self, request_id, attempts=20, delay=10):
        """Ожидание завершения генерации изображения."""
        print("⏳ Ожидание завершения генерации...")
        while attempts > 0:
            try:
                response = requests.get(self.URL + f'key/api/v1/text2image/status/{request_id}',
                                        headers=self.AUTH_HEADERS)
                response.encoding = 'utf-8'
                data = response.json()

                if data.get('status') == 'DONE':
                    print("✅ Изображение сгенерировано!")
                    return data.get('images', [])

                print(f"⌛ Статус генерации: {data.get('status')} (ожидание {delay} сек.)")
                attempts -= 1
                time.sleep(delay)

            except requests.exceptions.RequestException as e:
                print(f"❌ Ошибка при проверке статуса генерации: {e}")
                return []

        print("❌ Превышено время ожидания генерации изображения.")
        return []

    @staticmethod
    def decode_image(base64_string):
        """Декодирование изображения из base64."""
        try:
            image_data = base64.b64decode(base64_string)
            return Image.open(BytesIO(image_data))
        except Exception as e:
            print(f"❌ Ошибка декодирования изображения: {e}")
            return None


def generate_qr_code(data, size=300):
    """Создаёт QR-код с минимальными отступами и мягкими краями."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1,  # Уменьшаем отступы вокруг QR-кода
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill="black", back_color="white").convert("RGBA")

    # Обрезаем белые края
    bbox = qr_img.getbbox()
    qr_img = qr_img.crop(bbox)

    # Делаем изображение с альфа-каналом (прозрачность)
    qr_img = qr_img.resize((size, size), Image.LANCZOS)

    # Добавляем закругленные края
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size, size), radius=30, fill=255)  # Радиус закругления
    qr_img.putalpha(mask)

    # Делаем немного прозрачным (на 90%)
    qr_img = qr_img.convert("RGBA")
    alpha = qr_img.split()[3]
    alpha = alpha.point(lambda p: p * 0.9)  # 90% прозрачности
    qr_img.putalpha(alpha)

    return qr_img


def overlay_qr_on_image(background, qr_code):
    """Накладывает QR-код по центру фонового изображения."""
    bg_width, bg_height = background.size
    qr_width, qr_height = qr_code.size

    position = ((bg_width - qr_width) // 2, (bg_height - qr_height) // 2)

    # Создаём новый слой, чтобы мягко наложить QR-код
    overlay = Image.new("RGBA", background.size, (0, 0, 0, 0))
    overlay.paste(qr_code, position, qr_code)

    # Объединяем изображение с прозрачным QR-кодом
    return Image.alpha_composite(background.convert("RGBA"), overlay)


if __name__ == '__main__':
    # 🔹 Введите свои API-ключи
    API_URL = 'https://api-key.fusionbrain.ai/'
    API_KEY = '6AAC667DF487820133143F17037CBB54'
    SECRET_KEY = '7E55DE7139607DED7C9CB8FF604A3D25'

    # 🔹 Создаём объект API
    api = Text2ImageAPI(API_URL, API_KEY, SECRET_KEY)

    # 🔹 Получаем ID модели
    model_id = api.get_model()

    if model_id is None:
        print("❌ Ошибка: не удалось получить ID модели. Проверьте API-ключи!")
        exit()

    # 🔹 Запрос ссылки у пользователя
    qr_link = input("🔗 Введите ссылку для QR-кода: ").strip()

    if not qr_link:
        print("❌ Ошибка: ссылка не может быть пустой!")
        exit()

    # 🔹 Запрос промта у пользователя
    prompt = input("📝 Введите описание изображения (промт): ").strip()

    if not prompt:
        print("❌ Ошибка: промт не может быть пустым!")
        exit()

    # 🔹 Запрос на генерацию изображения
    uuid = api.generate(prompt, model_id)

    if uuid is None:
        print("❌ Ошибка: не удалось запустить генерацию.")
        exit()

    # 🔹 Ожидание завершения генерации
    images = api.check_generation(uuid)

    if not images:
        print("❌ Ошибка: изображение не было сгенерировано.")
        exit()

    # 🔹 Декодируем изображение
    base64_image = images[0]
    background_img = api.decode_image(base64_image)

    if background_img is None:
        print("❌ Ошибка: не удалось декодировать изображение.")
        exit()

    # 🔹 Создаём QR-код с введённой ссылкой
    qr_code_img = generate_qr_code(qr_link, size=300)

    # 🔹 Накладываем QR-код на изображение
    final_img = overlay_qr_on_image(background_img, qr_code_img)

    # 🔹 Показываем и сохраняем изображение
    final_img.show()
    final_img.save("final_result.png")
    print("✅ Финальное изображение сохранено как final_result.png")
