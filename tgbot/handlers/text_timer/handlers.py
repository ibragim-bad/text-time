from datetime import timedelta
import re

from django.utils.timezone import now
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, ConversationHandler

from tgbot.handlers.admin import static_text
from tgbot.models import User

def count_clean_text_len(text):
    clean_text = re.sub(r'[^\w\s]', '', text)
    text_len = len(list(filter(lambda x: len(x) > 1, clean_text.split())))
    return text_len

STATIC_TEXT_LEN = count_clean_text_len(static_text.test_text)

def check_len(update: Update, context: CallbackContext) -> None:
    """ Check time for text """
    u = User.get_user(update, context)
    # if not u.is_admin:
    #     update.message.reply_text(static_text.only_for_admins)
    #     return
    print(f'get_message from: {u.username}')
    text_len = count_clean_text_len(update.message.text)

    sec = int(text_len/u.word_seconds)
    time_for_text = str(timedelta(seconds=sec))
    update.message.reply_text(time_for_text)

def send_test_text(update: Update, context: CallbackContext):
    u = User.get_user(update, context)
    update.message.reply_text(
        'Пожалуйста продиктуйте в аудио следующий текст:'
    )

    context.bot.send_message(
        chat_id=u.user_id,
        text=static_text.test_text,
    )
    return 0

def set_time_audio(update: Update, context: CallbackContext):
    u = User.get_user(update, context)
    u.word_seconds = round(STATIC_TEXT_LEN/update.message.voice.duration, 3)
    u.save()
    print(f'set duration {u.word_seconds} for {u.username}')
    update.message.reply_text(
        'Установлена индивидуальная длительность текста'
    )
    return ConversationHandler.END
