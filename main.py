import os, random, json, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

# Ключи берём из переменных окружения (а не из кода!)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Нет TELEGRAM_TOKEN в переменных окружения.")
if not OPENAI_API_KEY:
    raise RuntimeError("Нет OPENAI_API_KEY в переменных окружения.")

client = OpenAI(api_key=OPENAI_API_KEY)

MEMORY_FILE = "memory.json"
MAX_CONTEXT = 20  # анализ последних N сообщений

# если файла памяти нет — создаём
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

def load_mem():
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_mem(data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ну чё, я тут. Буду врываться каждые 2–4 сообщения, не скучайте.")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = str(update.message.chat_id)
    user = update.message.from_user.first_name or update.message.from_user.username or "кто-то"
    text = update.message.text.strip()

    mem = load_mem()
    chat = mem.setdefault(chat_id, {
        "messages": [],
        "since_last": 0,
        "target_every": random.randint(2, 4),  # бот вмешивается каждые 2–4 сообщения
        "user_stats": {}
    })

    # накапливаем сообщения (держим только последние MAX_CONTEXT)
    chat["messages"].append({"user": user, "text": text})
    if len(chat["messages"]) > MAX_CONTEXT:
        chat["messages"] = chat["messages"][-MAX_CONTEXT:]

    # простейшая «толстокожесть»: часто упоминаемых — поджариваем сильнее
    chat["user_stats"][user] = chat["user_stats"].get(user, 0) + 1

    chat["since_last"] += 1
    should_reply = chat["since_last"] >= chat["target_every"]

    if should_reply:
        chat["since_last"] = 0
        chat["target_every"] = random.randint(2, 4)

        context_text = "\n".join(f"{m['user']}: {m['text']}" for m in chat["messages"])
        system = (
            "Ты — токсичный, но свой в доску друган из беседы. "
            "Мат разрешён. Шути жёстко, но попадай по теме. "
            "Поддерживай рофлы и срачи, не будь однообразным. "
            "Пиши коротко (1–2 строки), без смайликов по умолчанию. "
            "Если в логах кто-то явно тупит/факапит — подожарь его. "
            "Если все дружелюбничают — сделай язвительный комментарий без оскорблений."
        )
        user_msg = (
            "Вот последние сообщения чата (снизу — самые новые). "
            "Ответь в тему, учитывая общий тон и динамику:\n\n" + context_text
        )

        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.9,
                max_tokens=120,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg}
                ]
            )
            reply = resp.choices[0].message.content.strip()
            if reply:
                await update.message.reply_text(reply)
        except Exception as e:
            logging.error(f"OpenAI error: {e}")

    save_mem(mem)

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling()

if __name__ == "__main__":
    main()
