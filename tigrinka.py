#!/usr/bin/env python
import logging
import os
import random

from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater

import pymongo

logger = logging.getLogger(__name__)

TOKEN = '147645482:AAEwfBMbjaRZq4TgyCJEbOK8o0R6KmDy1-A'

class Tigrinka(object):
    RANDOM_STYLE = -1

    def __init__(self):
        self._client = pymongo.MongoClient()
        self._db = self._client.tigrinka
        self._styles = Tigrinka.read_styles()

    @staticmethod
    def read_styles():
        return [os.path.join('styles', filename) for filename in os.listdir('styles')]

    def get_user_status(self, chat_id):
        cursor = self._db.user_statuses.find({'chat_id': chat_id})
        if cursor.count() == 0:
            status = 'new'
            self._db.user_statuses.insert_one({'chat_id': chat_id, 'status': status})
        else:
            assert cursor.count() == 1
            status = cursor.next()['status']
        return status

    def get_style(self, chat_id):
        cursor = self._db.user_styles.find({'chat_id': chat_id})
        if cursor.count() == 0:
            style = Tigrinka.RANDOM_STYLE
            self._db.user_styles.insert_one({'chat_id': chat_id, 'style': style})
        else:
            assert cursor.count() == 1
            style = cursor.next()['style']
        return style

    def handle_photo_message(self, bot, update):
        file_id = update.message.photo[-1].file_id
        filename = './pictures/%s' % file_id
        logger.debug('Downloading photo %s', file_id)
        bot.getFile(file_id=file_id).download(filename)

        style = self.get_style(update.message.chat_id)
        if style == Tigrinka.RANDOM_STYLE:
            style = random.randint(0, len(self._styles) - 1)

        logger.info('Should start neuro-magic on photo %s and style %s', filename, self._styles[style])

        bot.sendMessage(update.message.chat_id, 'Sorry, neuro-magic is not implemented yet')

    def start(self):
        updater = Updater(token=TOKEN)
        dispatcher = updater.dispatcher

        # text_message_handler = MessageHandler([Filters.text], textMessageHandling)
        photo_message_handler = MessageHandler([Filters.photo], self.handle_photo_message)

        dispatcher.add_handler(photo_message_handler)

        updater.start_polling()

# def textMessageHandling(bot, update):
#     bot.sendMessage(chat_id=update.message.chat_id, text='Hey-ho')


def main():
    logging.basicConfig(level=logging.DEBUG)
    tigrinka = Tigrinka()
    tigrinka.start()

if __name__ == "__main__":
    main()
