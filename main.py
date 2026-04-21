import os
import telebot
import sqlite3
from groq import Groq

# রেলওয়ে ভেরিয়েবল
TELEGRAM_TOKEN = os.environ.get('8419644687:AAHFEl5BPFAnBtn6H2dDo93rMUsHKbvqHME')
GROQ_API_KEY = os.environ.get('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')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ডাটাবেস পাথ (রেলওয়ে ভলিউমের জন্য)
DB_PATH = '/app/data/maya_life_memory.db'

def init_db():
    # ফোল্ডার যদি না থাকে তবে তৈরি করা (এরর এড়াতে)
    os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_log 
                     (user_id INTEGER, role TEXT, content TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(user_id, role, content):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_log VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

def load_memory(user_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    # এক মাস আগের কথা মনে রাখতে শেষ ২৫টি মেসেজ নিচ্ছি
    cursor.execute("SELECT role, content FROM chat_log WHERE user_id=? ORDER BY ROWID DESC LIMIT 25", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    messages = [{"role": "system", "content": "তুমি মায়া, মিষ্টি বাঙালি মেয়ে। তুমি সব মনে রাখো।"}]
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})
    return messages

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    save_to_db(user_id, "user", message.text)
    memory = load_memory(user_id)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=memory
        )
        reply = completion.choices[0].message.content
        save_to_db(user_id, "assistant", reply)
        bot.reply_to(message, reply)
    except Exception as e:
        print(f"Error: {e}")

init_db()
bot.infinity_polling()
