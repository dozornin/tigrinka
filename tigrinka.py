#!/usr/bin/env python
# coding=utf-8
import argparse
import json
import logging
import os
import random
from Queue import Queue

import pymongo
import subprocess

import shutil
from telegram.error import TelegramError
from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater
from telegram.ext.commandhandler import CommandHandler

logger = logging.getLogger(__name__)


class Tigrinka(object):
    TOKEN = '147645482:AAEwfBMbjaRZq4TgyCJEbOK8o0R6KmDy1-A'
    RANDOM_STYLE = 'random'

    def __init__(self, styles_dir=None, working_dir=None, neural_style_dir=None):
        self._client = pymongo.MongoClient()
        self._db = self._client.tigrinka
        self._styles = Tigrinka.read_styles()
        self._tasks = Queue()
        self._styles_dir = styles_dir or 'styles'
        assert os.path.exists(self._styles_dir)
        self._working_dir = working_dir or 'photos'
        if not os.path.exists(self._working_dir):
            os.makedirs(self._working_dir)
        self.neural_style_dir = neural_style_dir
        if self.neural_style_dir is not None:
            assert os.path.exists(self.neural_style_dir)

    @staticmethod
    def read_styles():
        return json.load(open('styles.json'))

    def get_style_filepath(self, style):
        return os.path.join(self._styles_dir, style['filename'].encode('utf8'))

    def send_style(self, bot, chat_id, style_index):
        caption = self._styles[style_index]['description']
        cursor = self._db.styles.find({'style_index': style_index})
        if cursor.count() != 0:
            document = cursor.next()
            file_id = document.get('file_id')
            if file_id is not None:
                try:
                    bot.sendPhoto(chat_id, file_id, caption=caption)
                    return
                except TelegramError as ex:
                    logger.info('Could not locate photo %s on Telegram servers: %s', file_id, ex)
        message = bot.sendPhoto(chat_id, open(self.get_style_filepath(self._styles[style_index]), 'rb'),
                                caption=caption.encode('utf8'))
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
        style_name = Tigrinka.RANDOM_STYLE
        if cursor.count() > 0:
            assert cursor.count() == 1
            style_name = cursor.next()['style']
        for style in self._styles:
            if style['command'] == style_name:
                return style
        self._db.user_styles.update_one({'chat_id': chat_id}, {'$set': {'style': Tigrinka.RANDOM_STYLE}}, upsert=True)
        style = self._styles[random.randint(0, len(self._styles) - 1)]
        return style

    def handle_photo_message(self, bot, update):
        chat_id = update.message.chat_id
        file_id = update.message.photo[-1].file_id
        tempdir = os.path.join(self._working_dir, file_id)
        os.makedirs(tempdir)
        filename = os.path.join(tempdir, 'input.jpg')
        logger.debug('Downloading photo %s', file_id)
        bot.getFile(file_id=file_id).download(filename)

        style = self.get_style(chat_id)
        style_filepath = self.get_style_filepath(style)

        logger.info('Should start neuro-magic on photo %s and style %s (%s)',
                    filename, style['command'], style_filepath)
        with open(os.path.join(tempdir, 'info.txt'), 'w') as output:
            print >> output, chat_id
            print >> output, style_filepath

        self._tasks.put(ProcessTask(chat_id, filename, style_filepath, tempdir, self.neural_style_dir))
        bot.sendMessage(chat_id, 'Приступаю... Дайте мне несколько минут.')

    def show_help(self, bot, update):
        self.handle_user(update)
        bot.sendMessage(update.message.chat_id, '''Send me a photo and I will send you a magic in reply, or use one of these commands:
            /styles — list all available styles
            /help — show this message
        ''')

    def list_styles(self, bot, update):
        chat_id = update.message.chat_id
        bot.sendMessage(chat_id, 'Можете выбрать один из следующих стилей.')
        for style_index in xrange(len(self._styles)):
            self.send_style(bot, chat_id, style_index)
            bot.sendMessage(chat_id, 'Чтобы использовать этот стиль, пришлите команду /style%d' % style_index)
        bot.sendMessage(chat_id, 'Чтобы использовать случайный стиль каждый раз, пришлите команду /stylerandom')

    def set_style(self, style):
        def func(bot, update):
            chat_id = update.message.chat_id
            description = style['description'] if style is not None else 'Random'
            logger.info('Setting style "%s" for chat %s' % (description, chat_id))

            self._db.user_styles.update({'chat_id': chat_id},
                                        {'$set':
                                             {'style':
                                                  style['command'] if style is not None else Tigrinka.RANDOM_STYLE}})
            bot.sendMessage(chat_id, 'Style is set to "%s"' % description)

        return func

    def start(self):
        updater = Updater(token=Tigrinka.TOKEN)
        dispatcher = updater.dispatcher

        for style in self._styles:
            dispatcher.add_handler(CommandHandler(style['command'], self.set_style(style)))
        dispatcher.add_handler(CommandHandler('stylerandom', self.set_style(None)))
        dispatcher.add_handler(CommandHandler('styles', self.list_styles))
        dispatcher.add_handler(CommandHandler('start', self.show_help))
        dispatcher.add_handler(CommandHandler('help', self.show_help))
        dispatcher.add_handler(MessageHandler([Filters.text], self.show_help))
        dispatcher.add_handler(MessageHandler([Filters.photo], self.handle_photo_message))

        updater.start_polling()
        updater.job_queue.put(self.process_tasks, 1)

    def process_tasks(self, bot):
        while not self._tasks.empty():
            if self._tasks.queue[0](bot):
                self._tasks.get()
            else:
                break


class ProcessTask(object):
    def __init__(self, chat_id, input_filename, style_filename, working_dir, neural_style_dir):
        self.chat_id = chat_id
        self.input_filename = input_filename
        self.style_filename = style_filename
        self.working_dir = working_dir
        self.output_filename = os.path.join(self.working_dir, 'output.jpg')
        self.neural_style_dir = neural_style_dir
        self.popen = None

    def __call__(self, bot):
        if self.popen is None:
            if self.neural_style_dir is None:
                bot.sendMessage(self.chat_id, 'Простите, ничего не получилось. Я разучился рисовать :(')
                return True
            else:
                self.popen = subprocess.Popen(
                    'th %(neural_style)s/neural_style.lua '
                    '-proto_file %(neural_style)s/models/VGG_ILSVRC_19_layers_deploy.prototxt '
                    '-model_file %(neural_style)s/models/VGG_ILSVRC_19_layers.caffemodel '
                    '-num_iterations 300 '
                    '-save_iter 300 '
                    '-style_image %(style)s '
                    '-content_image %(input)s '
                    '-output_image %(output)s' % dict(style=self.style_filename, input=self.input_filename,
                                                      output=self.output_filename, neural_style=self.neural_style_dir),
                    shell=True)
                return False
        else:
            result = self.popen.poll()
            if result is None:
                return False
            if result:
                logger.error('Subprocess returned code %d' % result)
            else:
                bot.sendMessage(self.chat_id, 'Вот что у меня получилось. Не судите строго.')
                bot.sendPhoto(self.chat_id, photo=open(self.output_filename, 'rb'))
                shutil.rmtree(self.working_dir)
            return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--styles', help='Styles directory')
    parser.add_argument('--path', help='Working dir')
    parser.add_argument('--neural', help='Neural-style dir')
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG)
    tigrinka = Tigrinka(styles_dir=args.styles, working_dir=args.path, neural_style_dir=args.neural)
    tigrinka.start()


if __name__ == "__main__":
    main()
