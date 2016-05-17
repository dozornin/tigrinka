#!/usr/bin/env python
# coding=utf-8
import logging
import os
import random

from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater

import pymongo
from telegram.ext.commandhandler import CommandHandler

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
        # TODO: consider using keys instead of indexes
        return [os.path.join('styles', filename) for filename in sorted(os.listdir('styles')) if
                filename.endswith('.jpg')]

    def get_user_status(self, chat_id):
        # TODO: save user name
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
        # TODO: delete old pictures
        file_id = update.message.photo[-1].file_id
        filename = './pictures/%s' % file_id
        logger.debug('Downloading photo %s', file_id)
        bot.getFile(file_id=file_id).download(filename)

        style = self.get_style(update.message.chat_id)
        if style == Tigrinka.RANDOM_STYLE:
            style = random.randint(0, len(self._styles) - 1)

        logger.info('Should start neuro-magic on photo %s and style %s', filename, self._styles[style])
        # TODO: make it async
        # TODO: implement
        bot.sendMessage(update.message.chat_id,
                        'Sorry, neuro-magic is not implemented yet. Here is your original photo.')
        bot.sendPhoto(update.message.chat_id, photo=file_id)

    @staticmethod
    def show_help(bot, update):
        bot.sendMessage(update.message.chat_id, '''Send me a photo and I will send you a magic in reply, or use one of these commands:
            /styles — list all available styles
            /help — show this message
        ''')

    def list_styles(self, bot, update):
        chat_id = update.message.chat_id
        bot.sendMessage(chat_id, 'You can choose one of the following styles.')
        for style_index, style in enumerate(self._styles):
            # TODO: don't send photos each time, use file_id
            bot.sendPhoto(chat_id, photo=open(style, 'rb'))
            bot.sendMessage(chat_id, 'To use this style send me command /style%d' % style_index)
        bot.sendMessage(chat_id, 'To use random style each time send me command /stylerandom')

    def set_style(self, style_index):
        def func(bot, update):
            chat_id = update.message.chat_id
            logger.info('Setting style %d for chat %s' % (style_index, chat_id))
            self._db.user_styles.update({'chat_id': chat_id}, {'$set': {'style': style_index}})
            bot.sendMessage(chat_id, 'Style is set to %s' % (style_index if style_index >= 0 else 'random'))

        return func

    def start(self):
        updater = Updater(token=TOKEN)
        dispatcher = updater.dispatcher

        # text_message_handler = MessageHandler([Filters.text], textMessageHandling)
        photo_message_handler = MessageHandler([Filters.photo], self.handle_photo_message)

        for style_index in xrange(len(self._styles)):
            dispatcher.add_handler(CommandHandler('style%d' % style_index, self.set_style(style_index)))
        dispatcher.add_handler(CommandHandler('stylerandom', self.set_style(-1)))
        dispatcher.add_handler(CommandHandler('styles', self.list_styles))
        dispatcher.add_handler(CommandHandler('start', self.show_help))
        dispatcher.add_handler(CommandHandler('help', self.show_help))
        dispatcher.add_handler(MessageHandler([Filters.text], Tigrinka.show_help))
        dispatcher.add_handler(photo_message_handler)

        updater.start_polling()


def main():
    logging.basicConfig(level=logging.DEBUG)
    tigrinka = Tigrinka()
    tigrinka.start()


if __name__ == "__main__":
    main()
