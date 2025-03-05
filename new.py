import json
import time
import requests
import base64
from io import BytesIO
from PIL import Image


class Text2ImageAPI:

    def __init__(self, url, api_key, secret_key):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }

    def get_model(self):
        response = requests.get(self.URL + 'key/api/v1/models', headers=self.AUTH_HEADERS)
        data = response.json()
        return data[0]['id']

    def generate(self, prompt, model, images=1, width=1024, height=1024):
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": f"{prompt}"
            }
        }

        data = {
            'model_id': (None, model),
            'params': (None, json.dumps(params), 'application/json')
        }
        response = requests.post(self.URL + 'key/api/v1/text2image/run', headers=self.AUTH_HEADERS, files=data)
        data = response.json()
        return data['uuid']

    def check_generation(self, request_id, attempts=10, delay=10):
        while attempts > 0:
            response = requests.get(self.URL + 'key/api/v1/text2image/status/' + request_id, headers=self.AUTH_HEADERS)
            data = response.json()
            if data['status'] == 'DONE':
                return data['images']  # Возвращает base64-изображения

            attempts -= 1
            time.sleep(delay)

    @staticmethod
    def open_image(base64_string):
        """Декодирует и открывает изображение из base64."""
        image_data = base64.b64decode(base64_string)
        image = Image.open(BytesIO(image_data))
        image.show()


if __name__ == '__main__':
    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', '6AAC667DF487820133143F17037CBB54', '7E55DE7139607DED7C9CB8FF604A3D25')
    model_id = api.get_model()
    uuid = api.generate("Sun in sky", model_id)
    images = api.check_generation(uuid)

    if images:
        base64_image = images[0]  # Берём первое изображение из списка
        api.open_image(base64_image)
    else:
        print("Ошибка: изображение не было сгенерировано.")
