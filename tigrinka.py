from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater

TOKEN = '147645482:AAEwfBMbjaRZq4TgyCJEbOK8o0R6KmDy1-A'


def textMessageHandling(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text='Hey-ho')


def photoMessageHandling(bot, update):
    file_id = update.message.photo[-1].file_id
    print file_id
    print bot.getFile(file_id=file_id).file_path
    bot.sendPhoto(chat_id=update.message.chat_id,
                  photo=bot.getFile(file_id=file_id).file_path)


def main():
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher

    text_message_handler = MessageHandler([Filters.text], textMessageHandling)
    photo_message_handler = MessageHandler([Filters.photo], photoMessageHandling)

    dispatcher.addHandler(text_message_handler)
    dispatcher.addHandler(photo_message_handler)

    updater.start_polling()


if __name__ == "__main__":
    main()
