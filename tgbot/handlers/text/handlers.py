from datetime import timedelta

from django.utils.timezone import now
from telegram import ParseMode, Update
from telegram.ext import CallbackContext

from tgbot.handlers.admin import static_text
from tgbot.models import User


def check_len(update: Update, context: CallbackContext) -> None:
    """ Show help info about all secret admins commands """
    u = User.get_user(update, context)
    # if not u.is_admin:
    #     update.message.reply_text(static_text.only_for_admins)
    #     return
    print(f'get_message from: {u.username}')
    text_len = len(update.message.text.split())
    sec = int(text_len//u.word_seconds)
    time_for_text = str(timedelta(seconds=sec))
    update.message.reply_text(time_for_text)