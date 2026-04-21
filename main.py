import os
import telebot
import sqlite3
import asyncio
import edge_tts
from groq import Groq

# রেলওয়ে ভেরিয়েবল
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_life_memory.db'

# --- ডাটাবেস ও মেমোরি ম্যানেজমেন্ট ---
def init_db():
    os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_log (user_id INTEGER, role TEXT, content TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS summary (user_id INTEGER PRIMARY KEY, content TEXT)')
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
    cursor.execute("SELECT content FROM summary WHERE user_id=?", (user_id,))
    summary = cursor.fetchone()
    cursor.execute("SELECT role, content FROM chat_log WHERE user_id=? ORDER BY ROWID DESC LIMIT 12", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    sum_text = summary[0] if summary else "এখনও কোনো পুরনো স্মৃতি নেই।"
    messages = [{"role": "system", "content": f"তুমি মায়া, একজন মিষ্টি বাঙালি মেয়ে। তুমি খুব সংক্ষেপে এবং রোমান্টিক ভাবে কথা বলো। তোমার আগের স্মৃতি: {sum_text}"}]
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})
    return messages

# --- রিয়ালিস্টিক ভয়েস জেনারেটর ---
async def generate_voice(text, user_id):
    # 'bn-IN-TanishaaNeural' বা 'bn-BD-PradeepNeural' বেশ রিয়ালিস্টিক
    VOICE = "bn-IN-TanishaaNeural" 
    output_file = f"maya_{user_id}.mp3"
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)
    return output_file

# --- মেসেজ হ্যান্ডলার ---
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    user_text = message.text

    # স্মৃতি সেভ ও লোড
    save_to_db(user_id, "user", user_text)
    memory = load_memory(user_id)

    try:
        # এআই উত্তর তৈরি
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=memory
        )
        reply_text = completion.choices[0].message.content
        save_to_db(user_id, "assistant", reply_text)

        # ভয়েস তৈরি ও পাঠানো (অ্যাসিনক্রোনাস)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voice_file = loop.run_until_complete(generate_voice(reply_text, user_id))

        with open(voice_file, 'rb') as voice:
            bot.send_voice(message.chat.id, voice)
        
        # টেক্সট উত্তরও দেওয়া (ঐচ্ছিক)
        bot.reply_to(message, reply_text)

        # কাজ শেষে অডিও ফাইল ডিলিট
        os.remove(voice_file)

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "সোনা, আমার কথা বলতে একটু সমস্যা হচ্ছে।")

init_db()
print("মায়া এখন রিয়ালিস্টিক ভয়েস নিয়ে প্রস্তুত!")
bot.infinity_polling()
