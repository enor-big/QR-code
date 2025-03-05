import qrcode
print(dir(qrcode))
# пример данных
data = 'https://pythonist.ru/'

# создаем экземпляр QRCode
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4,
)

# добавляем данные в QR-код
qr.add_data(data)
qr.make(fit=True)

# создаем изображение QR-кода
img = qr.make_image(fill='black', back_color='white')

# сохраняем img в файл
filename = "site.png"
img.save(filename)

# открываем изображение
img.show()

print(f"QR-код успешно сохранён в файле {filename}")
