import os
import telebot
import openai
from datetime import datetime

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8426311891:AAGHHGi2EQd2nkMlfZt1TVL9i8B_4K_WKE4"  # <- сюда твой токен
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ключ OpenAI через переменные окружения

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# ================= ОБРАБОТЧИКИ =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "🧠 Привет! Я AI бот и отвечаю на любые сообщения."
    )

@bot.message_handler(func=lambda m: True)
def chat(m):
    text = m.text.strip()
    try:
        r = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":text}]
        )
        ans = r.choices[0].message.content
    except Exception as e:
        ans = f"❌ Ошибка: {e}"
    bot.send_message(m.chat.id, ans)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    bot.infinity_polling()
