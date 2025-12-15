import telebot
import time

TOKEN = "8426311891:AAGHHGi2EQd2nkMlfZt1TVL9i8B_4K_WKE4"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет! Я бот, который всегда онлайн!")

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.send_message(message.chat.id, f"Вы написали: {message.text}")

while True:
    try:
        bot.infinity_polling()
    except Exception as e:
        print("Ошибка:", e)
        time.sleep(5)
