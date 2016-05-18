#!/usr/bin/env python
# coding=utf-8
import logging
import os
import random

from telegram.error import TelegramError
from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater

import pymongo
from telegram.ext.commandhandler import CommandHandler

logger = logging.getLogger(__name__)


class Tigrinka(object):
    TOKEN = '147645482:AAEwfBMbjaRZq4TgyCJEbOK8o0R6KmDy1-A'
    RANDOM_STYLE = -1

    def __init__(self):
        self._client = pymongo.MongoClient()
        self._db = self._client.tigrinka
        self._styles = Tigrinka.read_styles()
        self._updater = Updater(token=Tigrinka.TOKEN)
        self._job_queue = self._updater.job_queue

    @staticmethod
    def read_styles():
        # TODO: consider using keys instead of indexes
        return [os.path.join('styles', filename) for filename in sorted(os.listdir('styles')) if
                filename.endswith('.jpg')]

    def send_style(self, bot, chat_id, style_index):
        cursor = self._db.styles.find({'style_index': style_index})
        if cursor.count() != 0:
            document = cursor.next()
            file_id = document.get('file_id')
            if file_id is not None:
                try:
                    bot.sendPhoto(chat_id, file_id)
                    return
                except TelegramError as ex:
                    logger.info('Could not locate photo %s on Telegram servers: %s', file_id, ex)
        message = bot.sendPhoto(chat_id, open(self._styles[style_index]))
        file_id = message.photo[-1].file_id
        self._db.styles.update_one({'style_index': style_index}, {'$set': {'file_id': file_id}}, upsert=True)

    def handle_user(self, update):
        user = update.message.from_user
        self._db.user_info.update_one({'chat_id': update.message.chat_id},
                                      {'$set':
                                           {'username': user.username,
                                            'first_name': user.first_name,
                                            'last_name': user.last_name}},
                                      upsert=True)

    def get_style(self, chat_id):
        cursor = self._db.user_styles.find({'chat_id': chat_id})
        if cursor.count() == 0:
            style = Tigrinka.RANDOM_STYLE
            self._db.user_styles.update_one({'chat_id': chat_id, 'style': style}, upsert=True)
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

    def show_help(self, bot, update):
        self.handle_user(update)
        bot.sendMessage(update.message.chat_id, '''Send me a photo and I will send you a magic in reply, or use one of these commands:
            /styles — list all available styles
            /help — show this message
        ''')

    def list_styles(self, bot, update):
        chat_id = update.message.chat_id
        bot.sendMessage(chat_id, 'You can choose one of the following styles.')
        for style_index in xrange(len(self._styles)):
            self.send_style(bot, chat_id, style_index)
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
        dispatcher = self._updater.dispatcher

        for style_index in xrange(len(self._styles)):
            dispatcher.add_handler(CommandHandler('style%d' % style_index, self.set_style(style_index)))
        dispatcher.add_handler(CommandHandler('stylerandom', self.set_style(-1)))
        dispatcher.add_handler(CommandHandler('styles', self.list_styles))
        dispatcher.add_handler(CommandHandler('start', self.show_help))
        dispatcher.add_handler(CommandHandler('help', self.show_help))
        dispatcher.add_handler(MessageHandler([Filters.text], self.show_help))
        dispatcher.add_handler(MessageHandler([Filters.photo], self.handle_photo_message))

        self._updater.start_polling()


def main():
    logging.basicConfig(level=logging.DEBUG)
    tigrinka = Tigrinka()
    tigrinka.start()


if __name__ == "__main__":
    main()
