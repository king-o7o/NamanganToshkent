import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Set

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramNetworkError, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS: list[int] = [1189419672, 1602393068]
SOURCE_CHAT_IDS: Set[int] = {
    -1001433669620,  # @namangantoshkent24
    -1001327239978,  # @Namangantoshkent26
    -1001737181397,  # @Namangan_toshkent_taksi_29
}

DATA_FILE = Path("data.json")

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

if not BOT_TOKEN:
    log.critical("Необходимо указать BOT_TOKEN в переменных окружения!")
    exit()
if not ADMINS:
    log.warning("Переменная ADMINS не задана. Админ-команды не будут работать.")
if not SOURCE_CHAT_IDS:
    log.warning("Переменная SOURCE_CHATS не задана. Бот не будет пересылать сообщения.")


# --- УПРАВЛЕНИЕ ДАННЫМИ (JSON) ---
class DataManager:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        try:
            if not self.file_path.exists():
                self.file_path.parent.mkdir(exist_ok=True)
                log.warning("Файл %s не найден, создаю пустой.", self.file_path)
                # ИЗМЕНЕНО: Добавили настройку по умолчанию для удаления сообщений
                default_data = {"recipients": [], "keywords": [], "ignored_users": [], "delete_source_message": False}
                self.file_path.write_text(json.dumps(default_data, indent=2, ensure_ascii=False))
                return default_data

            loaded_data = json.loads(self.file_path.read_text(encoding="utf-8"))
            # ИЗМЕНЕНО: Проверяем наличие всех ключей, включая новый
            for key, default_value in [
                ("recipients", []), 
                ("keywords", []), 
                ("ignored_users", []), 
                ("delete_source_message", False)
            ]:
                if key not in loaded_data:
                    loaded_data[key] = default_value
            return loaded_data
        except (json.JSONDecodeError, IOError) as e:
            log.exception("Не удалось прочитать или создать %s. Использую пустые списки. Ошибка: %s", self.file_path, e)
            return {"recipients": [], "keywords": [], "ignored_users": [], "delete_source_message": False}

    def _save(self) -> None:
        try:
            self.file_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
        except IOError as e:
            log.exception("Не удалось сохранить данные в %s. Ошибка: %s", self.file_path, e)

    @property
    def recipients(self) -> List[int]: return self.data.get("recipients", [])
    @property
    def keywords(self) -> List[str]: return self.data.get("keywords", [])
    @property
    def ignored_users(self) -> List[int]: return self.data.get("ignored_users", [])
    # НОВОЕ: Свойство для получения настройки удаления
    @property
    def delete_source(self) -> bool: return self.data.get("delete_source_message", False)

    def add_item(self, list_name: str, item: Any) -> bool:
        if item not in self.data[list_name]:
            self.data[list_name].append(item)
            self._save()
            log.info("В список '%s' добавлен элемент: %s", list_name, item)
            return True
        return False

    def remove_item(self, list_name: str, item: Any) -> bool:
        if item in self.data[list_name]:
            self.data[list_name].remove(item)
            self._save()
            log.info("Из списка '%s' удален элемент: %s", list_name, item)
            return True
        return False
    
    # НОВОЕ: Метод для переключения флага
    def toggle_delete_source(self) -> bool:
        current_state = self.delete_source
        self.data["delete_source_message"] = not current_state
        self._save()
        log.info("Настройка 'delete_source_message' изменена на %s", not current_state)
        return not current_state


db = DataManager(DATA_FILE)
router = Router()


# --- ДЕКОРАТОР ДЛЯ ПРОВЕРКИ АДМИНА ---
def admin_only(handler):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMINS:
            return await message.reply("⛔️ Сизда етарли ҳуқуқ йўқ.")
        return await handler(message, *args, **kwargs)

    return wrapper


# --- ОСНОВНЫЕ ХЭНДЛЕРЫ ---
@router.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def cmd_start(message: Message) -> None:
    text = f"👋 Ассалому алейкум!\nСизнинг ID: <code>{message.from_user.id}</code>"
    if message.from_user.id in ADMINS:
        # ИЗМЕНЕНО: Добавили новые команды в справку
        text += "\n\nСиз бот администраторисиз. Доступные команды:\n\n" \
                "<b>⚙️ Общие:</b>\n" \
                "/status - текущий статус бота\n" \
                "/toggle_delete - вкл/выкл удаление сообщений из чата-источника\n\n" \
                "<b>👥 Получатели:</b>\n" \
                "/add <code>user_id</code> - добавить получателя\n" \
                "/remove <code>user_id</code> - удалить получателя\n" \
                "/list - список получателей\n\n" \
                "<b>🚫 Блок-слова:</b>\n" \
                "/add_word <code>слово</code> - добавить блок-слово\n" \
                "/remove_word <code>слово</code> - удалить блок-слово\n" \
                "/list_words - список блок-слов\n\n" \
                "<b>IGNORE Игнор-лист:</b>\n" \
                "/add_ignore <code>user_id</code> - добавить юзера в игнор\n" \
                "/remove_ignore <code>user_id</code> - удалить юзера из игнора\n" \
                "/list_ignored - список игнорируемых"
    await message.answer(text)

# ИЗМЕНЕНО: Хэндлер `relay_message` теперь удаляет сообщения и обрабатывает ошибки
@router.message(F.chat.id.in_(SOURCE_CHAT_IDS), F.text)
async def relay_message(message: Message, bot: Bot) -> None:
    if message.from_user and message.from_user.id in db.ignored_users:
        log.info("Сообщение от игнорируемого пользователя %d пропущено.", message.from_user.id)
        return

    txt = (message.text or "").lower()
    if any(kw in txt for kw in db.keywords):
        log.info("Сообщение %d из чата %d пропущено из-за блок-слова.", message.message_id, message.chat.id)
        return

    for user_id in db.recipients:
        try:
            await bot.forward_message(
                chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id,
            )
            info_text = build_info_text(message)
            await bot.send_message(
                chat_id=user_id, text=info_text, disable_web_page_preview=True,
            )
        # НОВОЕ: Улучшенная обработка ошибок
        except TelegramForbiddenError:
            log.warning("Пользователь %d заблокировал бота. Удаляю из списка получателей.", user_id)
            db.remove_item("recipients", user_id)
        except Exception as e:
            log.exception("Не удалось переслать сообщение получателю %s. Ошибка: %s", user_id, e)
    
    # НОВОЕ: Блок для удаления исходного сообщения
    if db.delete_source:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            log.info("Исходное сообщение %d из чата %d успешно удалено.", message.message_id, message.chat.id)
        except Exception as e:
            log.error(
                "Не удалось удалить сообщение %d из чата %d. Проверьте права администратора! Ошибка: %s",
                message.message_id, message.chat.id, e
            )


def build_info_text(message: Message) -> str:
    user = message.from_user
    full_name = (user.full_name or "—").replace("<", "&lt;").replace(">", "&gt;")
    username = f"@{user.username}" if user.username else "Йоқ"
    link = f"https://t.me/c/{abs(message.chat.id) - 1000000000000}/{message.message_id}"
    return (f"✅ Мижоз ҳақида маълумот:\n"
            f"👤 Исм — <a href=\"tg://user?id={user.id}\">{full_name}</a> (ID: <code>{user.id}</code>)\n"
            f"💬 Username — {username}\n\n"
            f"🔗 <a href='{link}'>Асосий хабарга ўтиш</a>")


# --- АДМИН-ПАНЕЛЬ ---
# НОВОЕ: Команда для переключения режима удаления
@router.message(Command("toggle_delete"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_toggle_delete(message: Message):
    new_state = db.toggle_delete_source()
    status_text = "✅ ВКЛЮЧЕНО" if new_state else "❌ ВЫКЛЮЧЕНО"
    await message.reply(f"Автоматическое удаление исходных сообщений теперь: <b>{status_text}</b>.")

# НОВОЕ: Команда для просмотра статуса
@router.message(Command("status"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_status(message: Message):
    delete_status = "✅ ВКЛЮЧЕНО" if db.delete_source else "❌ ВЫКЛЮЧЕНО"
    
    recipients_list = "\n".join(f"  • <code>{uid}</code>" for uid in db.recipients) or "  Рўйхат бўш."
    keywords_list = "\n".join(f"  • <code>{word}</code>" for word in db.keywords) or "  Рўйхат бўш."
    ignored_list = "\n".join(f"  • <code>{uid}</code>" for uid in db.ignored_users) or "  Рўйхат бўш."

    text = (
        "<b>📊 Текущий статус бота:</b>\n\n"
        f"🗑️ <b>Удаление исходных сообщений:</b> {delete_status}\n\n"
        f"👥 <b>Получатели:</b>\n{recipients_list}\n\n"
        f"🚫 <b>Блок-слова:</b>\n{keywords_list}\n\n"
        f"IGNORE <b>Игнор-лист:</b>\n{ignored_list}"
    )
    await message.answer(text)


async def manage_id_list(message: Message, command: str, list_name: str, add_msg: str, remove_msg: str, list_title: str):
    parts = message.text.split(maxsplit=1)
    action = command.split('_')[0]

    if action == "list":
        item_list = db.data.get(list_name, [])
        if not item_list: return await message.reply("Рўйхат бўш.")
        rows = "\n".join(f"<code>{item}</code>" for item in item_list)
        return await message.reply(f"{list_title}:\n{rows}")

    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        return await message.reply(f"Фойдаланиш: /{command} [user_id]")

    uid = int(parts[1])
    if action == "add":
        if db.add_item(list_name, uid):
            await message.reply(f"✅ {add_msg}: <code>{uid}</code>")
        else:
            await message.reply("Бу ID рўйхатда аллақачон мавжуд.")
    elif action == "remove":
        if db.remove_item(list_name, uid):
            await message.reply(f"🗑 {remove_msg}: <code>{uid}</code>")
        else:
            await message.reply("Бу ID рўйхатда йўқ.")


@router.message(Command("add"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_add(message: Message, **kwargs): await manage_id_list(message, "add", "recipients", "Қўшилди", "", "")

@router.message(Command("remove"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_remove(message: Message, **kwargs): await manage_id_list(message, "remove", "recipients", "", "Ўчирилди", "")

@router.message(Command("list"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_list(message: Message, **kwargs): await manage_id_list(message, "list", "recipients", "", "", "Жорий қабул қилувчилар рўйхати")

@router.message(Command("add_ignore"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_add_ignore(message: Message, **kwargs):
    await manage_id_list(message, "add_ignore", "ignored_users", "Пользователь добавлен в игнор-лист", "", "")

@router.message(Command("remove_ignore"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_remove_ignore(message: Message, **kwargs):
    await manage_id_list(message, "remove_ignore", "ignored_users", "", "Пользователь удален из игнор-листа", "")

@router.message(Command("list_ignored"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_list_ignored(message: Message, **kwargs):
    await manage_id_list(message, "list", "ignored_users", "", "", "Игнорируемые пользователи")

@router.message(Command("add_word", "remove_word", "list_words"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def manage_keywords(message: Message, **kwargs):
    command, *args = message.text.split(maxsplit=1)
    command = command.lstrip('/')

    if command == "list_words":
        if not db.keywords: return await message.reply("Блок-сўзлар рўйхати бўш.")
        rows = "\n".join(f"• <code>{word}</code>" for word in db.keywords)
        return await message.reply(f"Жорий блок-сўзлар рўйхати:\n{rows}")

    if not args: return await message.reply(f"Фойдаланиш: /{command} [слово или фраза]")

    word = args[0].strip().lower()
    if command == "add_word":
        if db.add_item("keywords", word):
            await message.reply(f"✅ Блок-слово қўшилди: <code>{word}</code>")
        else:
            await message.reply("Бу сўз рўйхатда аллақачон мавжуд.")
    elif command == "remove_word":
        if db.remove_item("keywords", word):
            await message.reply(f"🗑 Блок-слово ўчирилди: <code>{word}</code>")
        else:
            await message.reply("Бу сўз рўйхатда йўқ.")


# --- ЗАПУСК БОТА ---1
async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(router)

    # Перед запуском бота, удалим старый файл data.json, если он не содержит новый ключ
    # чтобы избежать ошибок при первом запуске после обновления.
    # Это можно закомментировать после первого успешного запуска.
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        if 'delete_source_message' not in data:
            log.warning("Ключ 'delete_source_message' не найден в data.json. Файл будет пересоздан.")
            os.remove(DATA_FILE)
            # Переинициализируем db, чтобы он создал новый файл
            global db
            db = DataManager(DATA_FILE)
    except (FileNotFoundError, json.JSONDecodeError):
        pass # Файла нет или он пуст, DataManager справится

    while True:
        try:
            log.info("Запуск бота...")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

        except (KeyboardInterrupt, SystemExit):
            log.info("Бот остановлен вручную.")
            break

        except TelegramRetryAfter as e:
            log.warning("Flood-wait %s секунд.", e.retry_after)
            await asyncio.sleep(e.retry_after)

        except Exception:
            log.exception("Критическая ошибка, перезапуск через 15 секунд.")
            await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(main())
