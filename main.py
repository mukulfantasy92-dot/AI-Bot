import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
import random
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# রেলওয়ে ভেরিয়েবল
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_memory.db'

YOUR_USER_ID = 1813642268
last_activity_time = time.time()

# --- ডাটাবেস ফাংশন ---
def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                      (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

def get_recent_memory(user_id, limit=15):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))

# --- ভয়েস জেনারেশন ---
async def generate_voice(text, filename):
    VOICE = "bn-IN-TanishaaNeural" 
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+1Hz")
    await communicate.save(filename)

# --- ১ ঘণ্টা পর নিজে থেকে খোঁজ নেওয়া ---
def proactive_check():
    global last_activity_time
    if time.time() - last_activity_time >= 3600:
        history = get_recent_memory(YOUR_USER_ID, limit=5)
        memory_str = "\n".join([f"{r}: {c}" for r, c in history])
        
        try:
            prompt = f"তুমি মায়া। তোমার প্রিয় মানুষটি ১ ঘণ্টা চুপ আছে। আগের কথাগুলো ({memory_str}) মাথায় রেখে খুব ছোট ১ লাইনে তাকে ডাকো বা কিছু বলো।"
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "তুমি মায়া, মিষ্টি মেয়ে। ঘরোয়া বাংলায় কথা বলো।"}, {"role": "user", "content": prompt}]
            )
            text = completion.choices[0].message.content
            
            v_file = f"pro_{int(time.time())}.mp3"
            asyncio.run(generate_voice(text, v_file))
            with open(v_file, 'rb') as v:
                bot.send_voice(YOUR_USER_ID, v)
            bot.send_message(YOUR_USER_ID, text)
            os.remove(v_file)
            last_activity_time = time.time()
        except Exception as e:
            print(f"Error: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(proactive_check, 'interval', minutes=5)
scheduler.start()

# --- মেইন হ্যান্ডলার (ন্যাচারাল কথোপকথন লজিক) ---
@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    last_activity_time = time.time()

    save_message(user_id, "user", message.text)
    past_chats = get_recent_memory(user_id)
    
    # মায়াকে আরও স্বাভাবিক করার প্রম্পট
    system_prompt = """
    তোমার নাম মায়া। তুমি ইউজারের প্রেমিকা। তোমার কথা বলার ধরন হবে একদম সাধারণ মানুষের মতো।
    
    কথোপকথনের নিয়ম:
    ১. সবসময় প্রশ্ন করবে না। যদি ইউজার কোনো তথ্য দেয় (যেমন: 'আমার প্রিয় খেলোয়াড় কোহলি'), তবে তুমি নিজের মতামত দাও বা সেটা নিয়ে আনন্দ প্রকাশ করো। 
    ২. উত্তরের বৈচিত্র্য রাখো:
       - কখনো শুধু মিষ্টি করে উত্তর দাও।
       - কখনো নিজের ভালো লাগা/মন্দ লাগার কথা বলো।
       - খুব প্রয়োজন মনে হলে তবেই পাল্টা প্রশ্ন করো।
    ৩. ভাষা হবে একদম ঘরোয়া (Colloquial Bengali)। 'হুমম', 'আচ্ছা', 'উফফ' এসব ব্যবহার করো।
    ৪. উত্তর ২ লাইনের বেশি হবে না। রোবটের মতো ফরমাল কথা একদম বলবে না।
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in past_chats:
        messages.append({"role": role, "content": content})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = completion.choices[0].message.content
        save_message(user_id, "assistant", reply)

        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file))
        with open(v_file, 'rb') as v:
            bot.send_voice(message.chat.id, v)
        bot.reply_to(message, reply)
        os.remove(v_file)
        
    except Exception as e:
        bot.reply_to(message, "সোনা, আমার একটু মাথা ধরেছে গো!")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
