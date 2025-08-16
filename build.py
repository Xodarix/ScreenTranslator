import PyInstaller.__main__
import os
import sys
import easyocr  # Імпортуємо, щоб знайти шлях до бібліотеки

# --- Переконайтесь, що назва файлу тут правильна ---
# Наприклад, 'translate_for_games_123.py'
main_script_name = 'translate_for_games.py'

# --- Назва фінальної програми ---
app_name = 'ScreenTranslator'

# --- Шлях до іконки (опціонально, залиште '' якщо немає) ---
# Іконка має бути у форматі .ico
icon_path = '' 

# -----------------------------------------------------------

if not os.path.exists(main_script_name):
    print(f"ПОМИЛКА: Основний файл '{main_script_name}' не знайдено!")
    input("Натисніть Enter для виходу...")
else:
    print(f"Запускаю PyInstaller для файлу '{main_script_name}'...")

    # 1. Програмно знаходимо шлях до встановленої бібліотеки easyocr
    easyocr_path = os.path.dirname(easyocr.__file__)

    # 2. Формуємо правильні прапорці для додавання даних easyocr
    
    # Обов'язково додаємо папку з моделями, вона має існувати
    add_data_flags = [
        '--add-data', f'{os.path.join(easyocr_path, "model")}{os.pathsep}easyocr/model'
    ]

    # Перевіряємо, чи існує папка user_network, і додаємо її лише за наявності
    user_network_path = os.path.join(easyocr_path, "user_network")
    
    if os.path.exists(user_network_path):
        print("Знайдено додаткову папку 'user_network', додаю до збірки...")
        add_data_flags.extend(['--add-data', f'{user_network_path}{os.pathsep}easyocr/user_network'])
    # 3. Формуємо список аргументів для PyInstaller
    pyinstaller_args = [
        '--noconfirm',
        '--name', app_name,
        '--windowed',  # Еквівалент --noconsole
        # '--onefile', # Рекомендую спочатку збирати в папку. Для одного файлу - розкоментуйте.
        
        # --- Додаємо всі можливі приховані імпорти для стабільності ---
        '--hidden-import', 'pystray._win32',
        '--hidden-import', 'PIL._tkinter_finder',
        '--hidden-import', 'pynput.keyboard._win32',
        '--hidden-import', 'pynput.mouse._win32',
        '--hidden-import', 'torch',
        '--hidden-import', 'skimage.io',
    ]

    # Додаємо прапорці для даних
    pyinstaller_args.extend(add_data_flags)

    # Додаємо шлях до іконки, якщо він вказаний
    if icon_path and os.path.exists(icon_path):
        pyinstaller_args.extend(['--icon', icon_path])

    # Додаємо назву основного файлу в кінець
    pyinstaller_args.append(main_script_name)

    try:
        # Запускаємо PyInstaller з нашими аргументами
        PyInstaller.__main__.run(pyinstaller_args)
        
        print("\nУСПІХ! Компіляцію завершено.")
        print(f"Ваша готова програма знаходиться в папці 'dist\\{app_name}'.")

    except Exception as e:
        print(f"\nСТАЛАСЯ ПОМИЛКА ПІД ЧАС КОМПІЛЯЦІЇ: {e}")

    input("\nНатисніть Enter для виходу...")