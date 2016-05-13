from telegram.ext import MessageHandler, Filters
from telegram.ext import Updater

updater = Updater(token='147645482:AAEwfBMbjaRZq4TgyCJEbOK8o0R6KmDy1-A')
dispatcher = updater.dispatcher

def textMessageHandling(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text='Hey-ho')

def photoMessageHandling(bot, update):
    pass

if __name__ == "__main__":
    text_message_handler = MessageHandler([Filters.text], textMessageHandling)
    dispatcher.addHandler(text_message_handler)

    photo_message_handler = MessageHandler([Filters.photo], photoMessageHandling)

    updater.start_polling()