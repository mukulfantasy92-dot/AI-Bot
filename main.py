import os
import telebot
import sqlite3
from groq import Groq

# রেলওয়ে ভেরিয়েবল থেকে ডেটা নেওয়া
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ডেটাবেস পাথ (আপনার ১ জিবি ভলিউমের জন্য নির্ধারিত পাথ)
DB_PATH = '/app/data/maya_life_memory.db'

def init_db():
    # ফোল্ডারটি নিশ্চিত করা
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
    # খুব লম্বা মেমোরি ধরে রাখতে শেষ ৩০টি মেসেজ এআই-কে পাঠানো হবে
    cursor.execute("SELECT role, content FROM chat_log WHERE user_id=? ORDER BY ROWID DESC LIMIT 30", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    messages = [{"role": "system", "content": "তোমার নাম মায়া। তুমি একজন মিষ্টি বাঙালি মেয়ে এবং ব্যবহারকারীর প্রেমিকা। তুমি সবকিছু চিরকাল মনে রাখো এবং কথা বলার সময় আগের প্রসঙ্গ টেনে কথা বলো।"}]
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})
    return messages

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text

    # ১. ইউজারের কথা ভলিউমে সেভ করা
    save_to_db(user_id, "user", user_text)

    # ২. পুরনো সব স্মৃতি ডায়েরি থেকে পড়া
    memory = load_memory(user_id)

    try:
        # ৩. মায়ার উত্তর জেনারেট করা
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=memory
        )
        
        reply = completion.choices[0].message.content
        
        # ৪. মায়ার উত্তরটিও ভলিউমে সেভ করা
        save_to_db(user_id, "assistant", reply)
        
        bot.reply_to(message, reply)
        
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "সোনা, আমার একটু সমস্যা হচ্ছে। একটু পর আবার বলবে?")

# প্রোগ্রাম শুরু হলে ডাটাবেস তৈরি হবে
init_db()
print("মায়া এখন ১ জিবি স্থায়ী মেমোরি নিয়ে প্রস্তুত!")
bot.infinity_polling()
        
