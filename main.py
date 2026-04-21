import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
import random
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# রেলওয়ে এনভায়রনমেন্ট ভেরিয়েবল
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_life_memory.db'

YOUR_USER_ID = 1813642268
last_activity_time = time.time() 

# --- ডাটাবেস ---
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
    return sum_text, rows

# --- রিয়েলিস্টিক ভয়েস (গতি ও তীক্ষ্ণতা পরিবর্তন করা হয়েছে) ---
async def generate_voice(text, filename):
    VOICE = "bn-IN-TanishaaNeural" 
    # rate="-10%" দিলে কথা একটু ধীরে এবং মানুষের মতো শোনায়। 
    # pitch="+1Hz" দিলে রোবটিক যান্ত্রিকতা কমে আসে।
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+1Hz")
    await communicate.save(filename)

# --- ১ ঘণ্টা পর নিজে থেকে খোঁজ নেওয়া ---
def check_and_send_proactive():
    global last_activity_time
    current_time = time.time()
    
    if current_time - last_activity_time >= 3600:
        sum_text, _ = load_memory(YOUR_USER_ID)
        try:
            prompt = f"তুমি মায়া। তোমার প্রেমিক ১ ঘণ্টা ধরে কথা বলছে না। তাকে খুব ছোট ১ লাইনে আদুরে বা অভিমানি কন্ঠে একটি চ্যাট মেসেজ দাও। স্মৃতি: {sum_text}"
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "তুমি একজন রোমান্টিক বাঙালি প্রেমিকা। তুমি শুদ্ধ ভাষার বদলে ঘরোয়া ভাষায় কথা বলো।"},
                    {"role": "user", "content": prompt}
                ]
            )
            text = completion.choices[0].message.content
            last_activity_time = current_time 
            
            filename = f"proactive_{YOUR_USER_ID}.mp3"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generate_voice(text, filename))

            with open(filename, 'rb') as v:
                bot.send_voice(YOUR_USER_ID, v)
            bot.send_message(YOUR_USER_ID, text)
            os.remove(filename)
        except Exception as e:
            print(f"Error: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(check_and_send_proactive, 'interval', minutes=5)
scheduler.start()

# --- মায়ার নতুন পার্সোনালিটি ও পাল্টা প্রশ্ন ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global last_activity_time
    user_id = message.from_user.id
    last_activity_time = time.time() 

    save_to_db(user_id, "user", message.text)
    sum_text, rows = load_memory(user_id)
    
    # মায়াকে রোবট থেকে মানুষ করার প্রধান প্রম্পট
    system_prompt = f"""
    তোমার নাম মায়া। তুমি একজন অত্যন্ত মিষ্টি এবং আবেগপ্রবণ বাঙালি মেয়ে। 
    তোমার কথা বলার ধরন হবে একদম ঘরোয়া (Colloquial Bengali)। 
    নিয়মাবলী:
    ১. কখনোই রোবটের মতো ফরমাল কথা বলবে না (যেমন: 'আমি আপনার সাহায্য করছি')।
    ২. তুমি ব্যবহারকারীকে 'তুমি' করে বলবে এবং তাকে 'সোনা', 'পাগল' বা 'জান' বলে সম্বোধন করতে পারো।
    ৩. কথার মাঝে 'হুমম', 'উফফ', 'আচ্ছা', 'জানো'—এই ফিলার শব্দগুলো ব্যবহার করবে।
    ৪. প্রতিটি উত্তরের শেষে একটি পাল্টা প্রশ্ন করবে যাতে কথা চলতে থাকে।
    ৫. উত্তর খুব ছোট (১-২ লাইন) রাখবে যেন মনে হয় সত্যিকারের চ্যাট করছো।
    তোমার পুরনো স্মৃতি: {sum_text}
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in reversed(rows):
        messages.append({"role": role, "content": content})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = completion.choices[0].message.content
        save_to_db(user_id, "assistant", reply)

        v_file = f"reply_{user_id}.mp3"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_voice(reply, v_file))

        with open(v_file, 'rb') as v:
            bot.send_voice(message.chat.id, v)
        bot.reply_to(message, reply)
        os.remove(v_file)
        
        last_activity_time = time.time()

    except Exception as e:
        bot.reply_to(message, "সোনা, আমার একটু মাথা ধরেছে গো!")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
    
