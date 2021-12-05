"""
    Telegram event handlers
"""
import sys
import logging
from typing import Dict

import telegram.error
from telegram import Bot, Update, BotCommand
from telegram.ext import (
    Updater, Dispatcher, Filters,
    CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler
)

from dtb.celery import app  # event processing in async mode
from dtb.settings import TELEGRAM_TOKEN, DEBUG

from tgbot.handlers.utils import files, error
from tgbot.handlers.admin import handlers as admin_handlers
from tgbot.handlers.location import handlers as location_handlers
from tgbot.handlers.onboarding import handlers as onboarding_handlers
from tgbot.handlers.broadcast_message import handlers as broadcast_handlers
from tgbot.handlers.text_timer import handlers as text_handlers
from tgbot.handlers.onboarding.manage_data import SECRET_LEVEL_BUTTON
from tgbot.handlers.broadcast_message.manage_data import CONFIRM_DECLINE_BROADCAST
from tgbot.handlers.broadcast_message.static_text import broadcast_command

import telegram.bot
from telegram.ext import messagequeue as mq


class MQBot(telegram.bot.Bot):
    '''A subclass of Bot which delegates send method handling to MQ'''
    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except:
            pass

    @mq.queuedmessage
    def send_message(self, *args, **kwargs):
        '''Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments'''
        return super(MQBot, self).send_message(*args, **kwargs)
        
def setup_dispatcher(dp):
    """
    Adding handlers for events from Telegram
    """
    # onboarding

    dp.add_handler(CommandHandler("start", onboarding_handlers.command_start))

    # admin commands
    dp.add_handler(CommandHandler("admin", admin_handlers.admin))
    dp.add_handler(CommandHandler("stats", admin_handlers.stats))
    dp.add_handler(CommandHandler('export_users', admin_handlers.export_users))

    # user commands
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('set', text_handlers.send_test_text)],
        states={
            0: [MessageHandler(Filters.voice, text_handlers.set_time_audio)],
            # 1: [MessageHandler(Filters.text & ~(Filters.command) , text_handlers.check_len)]
        },
        fallbacks=[CommandHandler('cancel', ConversationHandler.END)],
    )

    dp.add_handler(conv_handler)


    # dp.add_handler(CommandHandler("ask_location", location_handlers.ask_for_location))
    # dp.add_handler(MessageHandler(Filters.location, location_handlers.location_handler))

    # secret level
    # dp.add_handler(CallbackQueryHandler(onboarding_handlers.secret_level, pattern=f"^{SECRET_LEVEL_BUTTON}"))

    # broadcast message
    dp.add_handler(
        MessageHandler(Filters.regex(rf'^{broadcast_command}(/s)?.*'), broadcast_handlers.broadcast_command_with_message)
    )
    dp.add_handler(
        CallbackQueryHandler(broadcast_handlers.broadcast_decision_handler, pattern=f"^{CONFIRM_DECLINE_BROADCAST}")
    )

    dp.add_handler(MessageHandler(Filters.text & ~(Filters.command) , text_handlers.check_len))

    # files
    # dp.add_handler(MessageHandler(
    #     Filters.animation, files.show_file_id,
    # ))

    # handling errors
    dp.add_error_handler(error.send_stacktrace_to_tg_chat)

    # EXAMPLES FOR HANDLERS
    #dp.add_handler(MessageHandler(Filters.text, text_handlers.check_len))
    # dp.add_handler(MessageHandler(
    #     Filters.document, <function_handler>,
    # ))
    # dp.add_handler(CallbackQueryHandler(<function_handler>, pattern="^r\d+_\d+"))
    # dp.add_handler(MessageHandler(
    #     Filters.chat(chat_id=int(TELEGRAM_FILESTORAGE_ID)),
    #     # & Filters.forwarded & (Filters.photo | Filters.video | Filters.animation),
    #     <function_handler>,
    # ))

    return dp

from telegram.utils.request import Request

def run_pooling():
    """ Run bot in pooling mode """
    q = mq.MessageQueue(all_burst_limit=20, all_time_limit_ms=1000)
    # set connection pool size for bot 
    request = Request(con_pool_size=8)
    # Global variable - best way I found to init Telegram bot

    bot = MQBot(TELEGRAM_TOKEN, request=request, mqueue=q)

    updater = Updater(token=None, use_context=True, bot=bot)

    dp = updater.dispatcher
    dp = setup_dispatcher(dp)
    

    bot_info = bot.get_me()
    bot_link = f"https://t.me/" + bot_info["username"]

    print(f"Pooling of '{bot_link}' started")
    # it is really useful to send '👋' emoji to developer
    # when you run local test
    # bot.send_message(text='👋', chat_id=<YOUR TELEGRAM ID>)

    updater.start_polling()
    updater.idle()


import os

# for test purposes limit global throughput to 3 messages per 3 seconds
q = mq.MessageQueue(all_burst_limit=3, all_time_limit_ms=3000)
# set connection pool size for bot 
request = Request(con_pool_size=8)
# Global variable - best way I found to init Telegram bot

bot = MQBot(TELEGRAM_TOKEN, request=request, mqueue=q)
try:
    TELEGRAM_BOT_USERNAME = bot.get_me()["username"]
except telegram.error.Unauthorized:
    logging.error(f"Invalid TELEGRAM_TOKEN.")
    sys.exit(1)


@app.task(ignore_result=True)
def process_telegram_event(update_json):
    update = Update.de_json(update_json, bot)
    dispatcher.process_update(update)


def set_up_commands(bot_instance: Bot) -> None:
    langs_with_commands: Dict[str, Dict[str, str]] = {
        'en': {
            'start': 'Start django bot 🚀',
            'stats': 'Statistics of bot 📊',
            'admin': 'Show admin info ℹ️',
            'ask_location': 'Send location 📍',
            'broadcast': 'Broadcast message 📨',
            'export_users': 'Export users.csv 👥',
        },
        'ru': {
            'start': 'Запустить django бота 🚀',
            'stats': 'Статистика бота 📊',
            'admin': 'Показать информацию для админов ℹ️',
            'broadcast': 'Отправить сообщение 📨',
            'set': 'Установить индивидуальную длину',
        }
    }

    bot_instance.delete_my_commands()
    for language_code in langs_with_commands:
        bot_instance.set_my_commands(
            language_code=language_code,
            commands=[
                BotCommand(command, description) for command, description in langs_with_commands[language_code].items()
            ]
        )


# WARNING: it's better to comment the line below in DEBUG mode.
# Likely, you'll get a flood limit control error, when restarting bot too often
set_up_commands(bot)

n_workers = 0 if DEBUG else 2
dispatcher = setup_dispatcher(Dispatcher(bot, update_queue=None, workers=n_workers, use_context=True))
