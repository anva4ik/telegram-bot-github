import os
import telebot
import openai

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8426311891:AAGHHGi2EQd2nkMlfZt1TVL9i8B_4K_WKE4"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ключ OpenAI через переменные окружения

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# ================= ПАМЯТЬ =================
# Сохраняем последние сообщения для контекста (небольшой кеш)
chat_memory = {}  # {chat_id: [{"role": "user", "content": "..."}]}

MAX_MEMORY = 10  # сохраняем последние 10 сообщений на чат

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
    chat_id = m.chat.id

    # Инициализация памяти чата
    if chat_id not in chat_memory:
        chat_memory[chat_id] = []

    # Добавляем сообщение пользователя в память
    chat_memory[chat_id].append({"role": "user", "content": text})
    if len(chat_memory[chat_id]) > MAX_MEMORY:
        chat_memory[chat_id].pop(0)

    try:
        # GPT-4o-mini генерация ответа
        r = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=chat_memory[chat_id]
        )
        ans = r.choices[0].message.content

        # Сохраняем ответ в память
        chat_memory[chat_id].append({"role": "assistant", "content": ans})

    except openai.error.RateLimitError:
        ans = "❌ Превышен лимит OpenAI. Попробуйте позже."
    except Exception as e:
        ans = f"❌ Ошибка GPT: {e}"

    bot.send_message(chat_id, ans)

# ================= ЗАПУСК =================
if __name__ == "__main__":
    bot.infinity_polling()
