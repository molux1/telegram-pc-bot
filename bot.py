import telebot
import json
import logging
import os
import platform
import random
import string
import time
import re
from io import BytesIO
import pyautogui
import psutil ### <<< ДОБАВЛЕНО: Импорт для статуса ПК
import requests ### <<< ДОБАВЛЕНО: Импорт для проверки обновлений

# --- 1. НАСТРОЙКА ЛОГГИРОВАНИЯ И ВЕРСИИ ---
### <<< ДОБАВЛЕНО: Указываем текущую версию бота
CURRENT_VERSION = "1.0" 

logging.basicConfig(
    level=logging.INFO,
    format='🤖 ATREUS Bot [%(levelname)s] - %(asctime)s - %(funcName)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# --- 2. ЗАГРУЗКА НАСТРОЕК ---
try:
    with open('settings.json', 'r', encoding='utf-8') as f:
        settings = json.load(f)
        BOT_TOKEN = settings.get("telegram_token")
        OWNER_ID = int(settings.get("owner_id", 0))
        ### <<< ДОБАВЛЕНО: Загружаем URL репозитория
        GITHUB_REPO_URL = settings.get("github_repo_url")

    if not BOT_TOKEN or BOT_TOKEN == "СЮДА_ВСТАВЬТЕ_ВАШ_ТЕЛЕГРАМ_ТОКЕН":
        raise ValueError("Токен не найден в settings.json.")
    if OWNER_ID == 0:
        raise ValueError("owner_id не указан или равен 0 в settings.json.")

except (FileNotFoundError, ValueError, TypeError) as e:
    log.critical(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Ошибка загрузки настроек: {e}")
    exit()

bot = telebot.TeleBot(BOT_TOKEN)
log.info("✅ Бот успешно инициализирован. Владелец ID: %d. Версия: %s", OWNER_ID, CURRENT_VERSION)

# --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_user_info_string(message_or_user) -> str:
    # ... (эта функция без изменений) ...
    user = None
    if isinstance(message_or_user, telebot.types.Message):
        user = message_or_user.from_user
    elif isinstance(message_or_user, telebot.types.User):
        user = message_or_user
    else:
        return "User(Unknown)"
    username = f"@{user.username}" if user.username else "NoUsername"
    name_part = user.first_name if user.first_name else ""
    if user.last_name: name_part += f" {user.last_name}"
    return f"User(ID:{user.id}, {username}, Name:'{name_part.strip()}')"

USER_DB_FILE = 'users.txt'
upload_destination = {}

### <<< ИЗМЕНЕНО: Клавиатура теперь с кнопкой "Статус ПК" для владельца
def get_main_keyboard(message: telebot.types.Message):
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False, row_width=2)
    start_button = telebot.types.KeyboardButton("🟢 Старт 🟢")
    
    if is_owner(message):
        screenshot_button = telebot.types.KeyboardButton("📸 Скриншот")
        status_button = telebot.types.KeyboardButton("💻 Статус ПК")
        # Размещаем кнопки по два в ряд для красоты
        keyboard.add(screenshot_button, status_button)
    
    keyboard.add(start_button) # Кнопка старта всегда внизу
    return keyboard

def is_owner(message: telebot.types.Message) -> bool:
    return message.from_user.id == OWNER_ID

def add_user_to_db(message: telebot.types.Message):
    # ... (эта функция без изменений) ...
    user_id = message.from_user.id
    user_info = get_user_info_string(message)
    try:
        with open(USER_DB_FILE, 'r', encoding='utf-8') as f:
            if str(user_id) in f.read():
                return
        with open(USER_DB_FILE, 'a', encoding='utf-8') as f:
            f.write(f"ID: {user_id}, Info: {user_info}\n")
        log.info(f"👤 Пользователь добавлен в базу: {user_info}")
    except FileNotFoundError:
        with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
            f.write(f"ID: {user_id}, Info: {user_info}\n")
        log.info(f"🗂️ Файл {USER_DB_FILE} создан. Первый пользователь: {user_info}")

def set_system_volume(level: int) -> bool:
    # ... (эта функция без изменений) ...
    try:
        os_type = platform.system()
        if os_type == "Windows":
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            vol_range = volume.GetVolumeRange()
            target_db = vol_range[0] + (vol_range[1] - vol_range[0]) * level / 100.0
            volume.SetMasterVolumeLevel(target_db, None)
        elif os_type == "Linux":
            import alsaaudio
            mixer = alsaaudio.Mixer()
            mixer.setvolume(level)
        else:
            return False
        return True
    except Exception as e:
        log.error(f"Ошибка при изменении громкости: {e}")
        return False

# --- 4. ОСНОВНЫЕ ОБРАБОТЧИКИ КОМАНД ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    # ... (код без изменений, но теперь он будет показывать обновленную клавиатуру)
    add_user_to_db(message)
    user_info = get_user_info_string(message)
    log.info("CMD /start: Получен запрос от %s.", user_info)
    if is_owner(message):
        help_text = (
            "| 👑 *Привет, Владелец!* Вам доступны все команды и кнопки:\n\n"
            "| 🔊 */volumeup* `[процент]` - Изменить громкость\n"
            "| 🔈 */volumedown* `[процент]` - Изменить громкость\n"
            "| 📁 */download* `/путь/к/файлу` - Скачать файл\n"
            "| 📎 */upload* - Загрузить файл\n"
            "| 🔑 */pass* `<длина>` - Сгенерировать пароль"
        )
    else:
        help_text = (
            "| 👋 *Привет! Я твой бот-помощник.*\n\n"
            "| 🔐 Вам доступны следующие команды:\n\n"
            "| 🔑 */pass* `<длина>` - Сгенерировать пароль (например, `/pass 8`)\n"
            "| ℹ️ */help* - Показать это сообщение"
        )
    bot.reply_to(message, help_text, parse_mode='Markdown', reply_markup=get_main_keyboard(message))

@bot.message_handler(func=lambda message: message.text == "🟢 Старт 🟢")
def handle_start_button(message):
    # ... (этот блок без изменений) ...
    user_info = get_user_info_string(message)
    log.info("Button 'Старт': Нажата кнопка старта от %s.", user_info)
    send_welcome(message)

# --- Команды только для владельца ---

@bot.message_handler(commands=['screenshot'])
def handle_screenshot_command(message):
    handle_screenshot_request(message)

@bot.message_handler(func=lambda message: message.text == "📸 Скриншот")
def handle_screenshot_request(message):
    # ... (этот блок без изменений) ...
    user_info = get_user_info_string(message)
    log.info(f"Button 'Скриншот': Получен запрос от {user_info}")
    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} попытался сделать скриншот.")
        bot.reply_to(message, "⛔ У вас нет доступа к этой функции.")
        return
    try:
        bot.send_chat_action(message.chat.id, 'upload_photo')
        current_time = time.strftime('%H:%M:%S')
        caption_text = f"✅ Скриншот ({current_time})"
        screenshot = pyautogui.screenshot()
        bio = BytesIO()
        bio.name = 'screenshot.png'
        screenshot.save(bio, 'PNG')
        bio.seek(0)
        bot.send_photo(message.chat.id, photo=bio, caption=caption_text)
        log.info(f"✅ Скриншот успешно сделан и отправлен {user_info}.")
    except Exception as e:
        log.error(f"💥 Ошибка при создании или отправке скриншота для {user_info}: {e}")
        bot.reply_to(message, f"❌ Не удалось сделать скриншот: {e}")

### <<< ДОБАВЛЕНО: Новый обработчик для кнопки "Статус ПК"
@bot.message_handler(func=lambda message: message.text == "💻 Статус ПК")
def handle_status_pc_request(message):
    user_info = get_user_info_string(message)
    log.info(f"Button 'Статус ПК': Получен запрос от {user_info}")

    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} попытался получить статус ПК.")
        bot.reply_to(message, "⛔ У вас нет доступа к этой функции.")
        return
        
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        
        # 1. OS Info
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        
        # 2. Uptime
        boot_time_seconds = time.time() - psutil.boot_time()
        days, rem = divmod(boot_time_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{int(hours):02}ч {int(minutes):02}м {int(seconds):02}с"
        if days > 0:
            uptime_str = f"{int(days)}д " + uptime_str

        # 3. CPU
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # 4. RAM
        ram = psutil.virtual_memory()
        ram_total_gb = ram.total / (1024**3)
        ram_used_gb = ram.used / (1024**3)
        ram_info = f"{ram.percent}% ({ram_used_gb:.2f}/{ram_total_gb:.2f} GB)"
        
        # 5. Disks
        disk_lines = []
        partitions = psutil.disk_partitions()
        for part in partitions:
            # Пропускаем виртуальные диски и CD-ROM
            if 'cdrom' in part.opts or part.fstype == '':
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_total_gb = usage.total / (1024**3)
                disk_used_gb = usage.used / (1024**3)
                disk_lines.append(
                    f"   - Диск `{part.mountpoint}` ({part.fstype}): {usage.percent}% исп. "
                    f"({disk_used_gb:.1f}/{disk_total_gb:.1f} GB)"
                )
            except Exception:
                continue # Пропускаем диски, к которым нет доступа
        
        disk_info = "\n".join(disk_lines) if disk_lines else "   (Информация о дисках недоступна)"

        # Формируем и отправляем сообщение
        status_message = (
            f"🖥️ *Статус системы:*\n\n"
            f"  `OS:`   `{os_info}`\n"
            f"  `UpT:`  `{uptime_str}`\n"
            f"  `CPU:`  `{cpu_usage}%`\n"
            f"  `RAM:`  `{ram_info}`\n"
            f"  `Disk:`\n{disk_info}"
        )
        bot.reply_to(message, status_message, parse_mode='Markdown')
        log.info(f"✅ Статус ПК успешно отправлен {user_info}.")

    except Exception as e:
        log.error(f"💥 Ошибка при получении статуса ПК для {user_info}: {e}")
        bot.reply_to(message, f"❌ Не удалось получить статус ПК: {e}")

# ... (остальные ваши обработчики без изменений: handle_volume_control, download_file и т.д.) ...
@bot.message_handler(commands=['volumeup', 'volumedown'])
def handle_volume_control(message):
    user_info = get_user_info_string(message)
    command = message.text.split()[0]
    log.info(f"CMD {command}: Получен запрос от {user_info}")
    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} попытался использовать {command}.")
        bot.reply_to(message, "⛔ У вас нет доступа к этой команде.")
        return
    add_user_to_db(message)
    parts = message.text.split()
    target_level = None
    try:
        if len(parts) > 1:
            level_arg = parts[1]
            if not level_arg.isdigit():
                raise ValueError("Аргумент не является числом.")
            target_level = int(level_arg)
            log.info(f"Пользователь {user_info} указал громкость: {target_level}%")
            if not (0 <= target_level <= 100):
                bot.reply_to(message, "⚠️ Процент громкости должен быть от 0 до 100.")
                log.warning(f"⚠️ Некорректный процент громкости ({target_level}) от {user_info}.")
                return
        else:
            if command == '/volumeup':
                target_level = 100
            else:
                target_level = 0
            log.info(f"Процент не указан. Используется значение по умолчанию {target_level}% для {command}.")
        if set_system_volume(target_level):
            emoji = "🔊" if target_level > 50 else "🔉" if target_level > 0 else "🔈"
            bot.reply_to(message, f"{emoji} Громкость установлена на {target_level}%")
            log.info(f"✅ Громкость успешно установлена на {target_level}% для ПК.")
        else:
            bot.reply_to(message, "❌ Не удалось изменить громкость. Проверьте логи.")
            log.error(f"❌ Не удалось установить громкость на {target_level}% (запрошено {user_info}).")
    except ValueError:
        bot.reply_to(message, "❌ Ошибка: Пожалуйста, введите корректное число (от 0 до 100).")
        log.warning(f"⚠️ Нечисловое значение для громкости от {user_info}: '{parts[1]}'")
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла непредвиденная ошибка: {e}")
        log.error(f"💥 Непредвиденная ошибка в {command}: {e}")

@bot.message_handler(commands=['download'])
def download_file(message):
    user_info = get_user_info_string(message)
    log.info(f"CMD /download: Получен запрос от {user_info}")
    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} попытался использовать /download.")
        bot.reply_to(message, "⛔ У вас нет доступа к этой команде.")
        return
    add_user_to_db(message)
    try:
        path = message.text.split(' ', 1)[1].strip()
        log.info(f"📥 Пользователь {user_info} запросил файл по пути: '{path}'")
        if not path:
             bot.reply_to(message, "⚠️ Пожалуйста, укажите путь к файлу.")
             return
        if not os.path.exists(path):
            bot.reply_to(message, "🚫 Файл не найден по указанному пути.")
            log.warning(f"🚫 Файл не найден: '{path}' (запрошено {user_info}).")
            return
        if not os.path.isfile(path):
            bot.reply_to(message, "🚫 Указанный путь не является файлом (возможно, это папка).")
            log.warning(f"🚫 Путь не является файлом: '{path}' (запрошено {user_info}).")
            return
        file_size_mb = os.path.getsize(path) / (1024 * 1024)
        if file_size_mb > 50:
             bot.reply_to(message, "❌ Файл слишком большой. Лимит 50 МБ.")
             log.warning(f"❌ Файл '{path}' слишком большой ({file_size_mb:.2f} MB).")
             return
        bot.send_chat_action(message.chat.id, 'upload_document')
        with open(path, 'rb') as file:
            bot.send_document(message.chat.id, file, caption=f"📄 Ваш файл: `{os.path.basename(path)}`", parse_mode='Markdown')
        log.info(f"✅ Файл '{path}' успешно отправлен пользователю {user_info}.")
    except IndexError:
        bot.reply_to(message, "⚠️ Пожалуйста, укажите путь к файлу после команды.")
        log.warning(f"⚠️ Отсутствует аргумент пути в /download (запрошено {user_info}).")
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла непредвиденная ошибка: {e}")
        log.error(f"💥 Непредвиденная ошибка при отправке файла: {e}")

@bot.message_handler(commands=['upload'])
def upload_file_prompt(message):
    user_info = get_user_info_string(message)
    log.info(f"CMD /upload: Получен запрос от {user_info}")
    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} попытался использовать /upload.")
        bot.reply_to(message, "⛔ У вас нет доступа к этой команде.")
        return
    add_user_to_db(message)
    user_id = message.from_user.id
    default_path = os.getcwd() 
    upload_destination[user_id] = default_path
    bot.reply_to(message, f"📎 Теперь отправьте мне файл. Он будет сохранен в папку:\n`{default_path}`")
    log.info(f"📤 Пользователь {user_info} инициировал загрузку. Ожидание файла в '{default_path}'.")

@bot.message_handler(content_types=['document'])
def handle_document_upload(message):
    user_info = get_user_info_string(message)
    user_id = message.from_user.id
    if user_id not in upload_destination:
        log.warning(f"⚠️ Получен документ от {user_info}, но команда /upload не была вызвана.")
        return
    if not is_owner(message):
        log.warning(f"ACCESS DENIED: {user_info} отправил документ, не будучи владельцем.")
        del upload_destination[user_id]
        return
    dest_path = upload_destination[user_id]
    try:
        file_info = bot.get_file(message.document.file_id)
        original_filename = message.document.file_name
        log.info(f"📤 Начало загрузки файла '{original_filename}' от {user_info}.")
        bot.send_chat_action(user_id, 'typing') 
        downloaded_file_content = bot.download_file(file_info.file_path)
        save_path = os.path.join(dest_path, original_filename)
        counter = 1
        base_name, ext = os.path.splitext(original_filename)
        while os.path.exists(save_path):
             new_filename = f"{base_name}_{counter}{ext}"
             save_path = os.path.join(dest_path, new_filename)
             counter += 1
        log.info(f"💾 Сохранение файла как '{os.path.basename(save_path)}' в папку: {dest_path}")
        with open(save_path, 'wb') as new_file:
            new_file.write(downloaded_file_content)
        bot.reply_to(message, f"✅ Файл '{os.path.basename(save_path)}' успешно сохранен!")
        log.info(f"✅ Файл успешно сохранен по пути: {save_path} (от {user_info}).")
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка при загрузке файла: {e}")
        log.error(f"💥 Ошибка при загрузке файла от {user_info}: {e}")
    finally:
        if user_id in upload_destination:
            del upload_destination[user_id]
            log.info(f"🧹 Состояние ожидания загрузки для {user_info} очищено.")

@bot.message_handler(commands=['pass'])
def generate_password(message):
    # ... (этот блок без изменений) ...
    user_info = get_user_info_string(message)
    log.info(f"CMD /pass: Получен запрос от {user_info}")
    add_user_to_db(message)
    try:
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            raise IndexError("Отсутствует длина пароля.")
        length = int(parts[1].strip())
        log.info(f"🔑 Пользователь {user_info} указал длину: {length}")
        if not (8 <= length <= 64):
            bot.reply_to(message, "⚠️ Длина пароля должна быть от 8 до 64 символов.")
            log.warning(f"⚠️ Некорректная длина пароля ({length}) от {user_info}.")
            return
        chars = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(random.choice(chars) for _ in range(length))
        bot.reply_to(message, f"🔑 Ваш новый пароль ({length} симв.):\n\n`{password}`\n\n_(нажмите, чтобы скопировать)_", parse_mode='Markdown')
        log.info(f"✅ Пароль длиной {length} сгенерирован и отправлен пользователю {user_info}.")
    except (IndexError, ValueError):
        bot.reply_to(message, "🔐 Укажите длину пароля после команды. Пример:\n`/pass 16`")
        log.warning(f"⚠️ Некорректный или отсутствующий аргумент в /pass (запрошено {user_info}).")
    except Exception as e:
        bot.reply_to(message, f"❌ Произошла ошибка: {e}")
        log.error(f"💥 Непредвиденная ошибка в /pass: {e}")

### <<< ДОБАВЛЕНО: Функция проверки обновлений
def check_for_updates():
    if not GITHUB_REPO_URL:
        log.info("Проверка обновлений пропущена: 'github_repo_url' не указан в settings.json.")
        return

    try:
        # Формируем URL к raw-файлу version.txt
        # Пример: https://github.com/user/repo -> https://raw.githubusercontent.com/user/repo/main/version.txt
        version_url = GITHUB_REPO_URL.replace("github.com", "raw.githubusercontent.com") + "/main/version.txt"
        
        log.info(f"Проверка обновлений по URL: {version_url}")
        response = requests.get(version_url, timeout=5)
        response.raise_for_status() # Вызовет ошибку, если статус не 200 OK
        
        latest_version = response.text.strip()
        
        if latest_version > CURRENT_VERSION:
            log.warning(f"⬆️ Доступно новое обновление! Текущая: {CURRENT_VERSION}, Последняя: {latest_version}")
            update_message = (
                f"⬆️ *Доступно новое обновление для бота!* ⬆️\n\n"
                f"- Текущая версия: `{CURRENT_VERSION}`\n"
                f"- Новая версия: `{latest_version}`\n\n"
                f"Скачать обновление можно на GitHub:\n{GITHUB_REPO_URL}"
            )
            bot.send_message(OWNER_ID, update_message, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            log.info(f"✅ У вас установлена последняя версия бота ({CURRENT_VERSION}).")

    except Exception as e:
        log.error(f"💥 Не удалось проверить обновления: {e}")

# --- 5. ЗАПУСК БОТА ---
if __name__ == '__main__':
    log.info("🚀 Бот готов к работе. Начинаю polling...")
    try:
        check_for_updates() ### <<< ДОБАВЛЕНО: Проверяем обновления при старте
        bot.polling(none_stop=True)
    except Exception as e:
        log.critical(f"💥 КРИТИЧЕСКАЯ ОШИБКА POLLING. Бот остановлен: {e}")