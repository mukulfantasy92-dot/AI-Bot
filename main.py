import os
import telebot
import sqlite3
from groq import Groq

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_life_memory.db'

def init_db():
    os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    # চ্যাট লগের পাশাপাশি সামারি রাখার জন্য টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_log 
                     (user_id INTEGER, role TEXT, content TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS summary 
                     (user_id INTEGER PRIMARY KEY, content TEXT)''')
    conn.commit()
    conn.close()

def get_summary(user_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM summary WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "এখনও কোনো সারসংক্ষেপ নেই।"

def update_summary(user_id, new_chat_history):
    # এআই-কে দিয়ে পুরো আলাপের সারসংক্ষেপ তৈরি করা
    prompt = f"নিচের আলাপটি পড়ে ব্যবহারকারী সম্পর্কে গুরুত্বপূর্ণ তথ্যগুলো ছোট করে মনে রাখো (যেমন নাম, পছন্দ, কাজ): \n{new_chat_history}"
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": "তুমি একজন মেমোরি অ্যাসিস্ট্যান্ট। শুধু সারাংশটুকু লিখবে।"},
                  {"role": "user", "content": prompt}]
    )
    summary_text = completion.choices[0].message.content
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO summary (user_id, content) VALUES (?, ?)", (user_id, summary_text))
    conn.commit()
    conn.close()

def save_to_db(user_id, role, content):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_log VALUES (?, ?, ?)", (user_id, role, content))
    
    # যদি ৫০টির বেশি মেসেজ হয়ে যায়, তবে সামারি তৈরি করে পুরনো মেসেজ ডিলিট করবে
    cursor.execute("SELECT COUNT(*) FROM chat_log WHERE user_id=?", (user_id,))
    if cursor.fetchone()[0] > 50:
        cursor.execute("SELECT role, content FROM chat_log WHERE user_id=? LIMIT 40", (user_id,))
        rows = cursor.fetchall()
        history_str = "\n".join([f"{r}: {c}" for r, c in rows])
        update_summary(user_id, history_str)
        # পুরনো ৪০টি মেসেজ মুছে ফেলা
        cursor.execute("DELETE FROM chat_log WHERE ROWID IN (SELECT ROWID FROM chat_log WHERE user_id=? LIMIT 40)", (user_id,))
    
    conn.commit()
    conn.close()

def load_memory(user_id):
    summary = get_summary(user_id)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_log WHERE user_id=? ORDER BY ROWID DESC LIMIT 15", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    messages = [{"role": "system", "content": f"তোমার নাম মায়া। তুমি একজন মিষ্টি মেয়ে। ব্যবহারকারী সম্পর্কে তোমার দীর্ঘমেয়াদী স্মৃতি: {summary}"}]
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
    
