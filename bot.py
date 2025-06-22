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
async def cmd_add_ignore(message: Message, **kwargs): await manage_id_list(message, "add_ignore", "ignored_users", "Пользователь добавлен в игнор-лист", "", "")
@router.message(Command("remove_ignore"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_remove_ignore(message: Message, **kwargs): await manage_id_list(message, "remove_ignore", "ignored_users", "", "Пользователь удален из игнор-листа", "")
@router.message(Command("list_ignored"), F.chat.type == ChatType.PRIVATE)
@admin_only
async def cmd_list_ignored(message: Message, **kwargs): await manage_id_list(message, "list", "ignored_users", "", "", "Игнорируемые пользователи")

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
        if db.add_item("keywords", word): await message.reply(f"✅ Блок-слово қўшилди: <code>{word}</code>")
        else: await message.reply("Бу сўз рўйхатда аллақачон мавжуд.")
    elif command == "remove_word":
        if db.remove_item("keywords", word): await message.reply(f"🗑 Блок-слово ўчирилди: <code>{word}</code>")
        else: await message.reply("Бу сўз рўйхатда йўқ.")

# --- ЗАПУСК БОТА ---
async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.include_router(router)

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

if name == "main":
    asyncio.run(main())
