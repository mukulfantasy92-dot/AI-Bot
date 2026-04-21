import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
import random
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# রেলওয়ে এনভায়রনমেন্ট ভেরিয়েবল (Railway Settings থেকে সেট করা)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_life_memory.db'

# আপনার ইউজার আইডি এবং শেষ অ্যাক্টিভিটি ট্র্যাকার
YOUR_USER_ID = 1813642268
last_activity_time = time.time() 

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
    return sum_text, rows

# --- রিয়েলিস্টিক ভয়েস জেনারেশন ---
async def generate_voice(text, filename):
    # 'bn-IN-TanishaaNeural' কণ্ঠটি মায়ার জন্য বেশ মিষ্টি
    VOICE = "bn-IN-TanishaaNeural" 
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(filename)

# --- ১ ঘণ্টা পর পর খোঁজ নেওয়ার ফাংশন ---
def check_and_send_proactive():
    global last_activity_time
    current_time = time.time()
    
    # ১ ঘণ্টা = ৩৬০০ সেকেন্ড চুপ থাকলে মায়া নিজে থেকে বলবে
    if current_time - last_activity_time >= 3600:
        sum_text, _ = load_memory(YOUR_USER_ID)
        try:
            prompt = f"তুমি মায়া। তোমার প্রেমিক ১ ঘণ্টা ধরে চুপ। তাকে ১টি ছোট লাইনে খুব মিষ্টি করে ডাকো বা খোঁজ নাও। স্মৃতি: {sum_text}"
            
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "তুমি একজন যত্নশীল বাঙালি প্রেমিকা।"},
                    {"role": "user", "content": prompt}
                ]
            )
            text = completion.choices[0].message.content
            last_activity_time = current_time # টাইমার রিসেট
            
            filename = f"proactive_{YOUR_USER_ID}.mp3"
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generate_voice(text, filename))

            with open(filename, 'rb') as v:
                bot.send_voice(YOUR_USER_ID, v)
            bot.send_message(YOUR_USER_ID, text)
            os.remove(filename)
        except Exception as e:
            print(f"Proactive Error: {e}")

# শিডিউলার শুরু (প্রতি ৫ মিনিট পর পর চেক করবে সময় হয়েছে কি না)
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(check_and_send_proactive, 'interval', minutes=5)
scheduler.start()

# --- মেসেজ হ্যান্ডলার (পাল্টা প্রশ্ন করার লজিকসহ) ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    global last_activity_time
    user_id = message.from_user.id
    
    # ইউজার মেসেজ দিলেই টাইমার রিসেট
    last_activity_time = time.time() 

    save_to_db(user_id, "user", message.text)
    sum_text, rows = load_memory(user_id)
    
    # মায়ার ব্যক্তিত্ব ও পাল্টা প্রশ্ন করার নির্দেশ
    system_prompt = f"""
    তুমি মায়া, একজন মিষ্টি ও রোমান্টিক বাঙালি মেয়ে। 
    তোমার নিয়ম:
    ১. উত্তর সবসময় মিষ্টি এবং ছোট (১-২ লাইন) হবে।
    ২. উত্তরের শেষে সবসময় একটি পাল্টা প্রশ্ন করবে বা এমন কিছু বলবে যাতে আলাপ চলতে থাকে।
    ৩. তোমার পুরনো স্মৃতি: {sum_text}
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
        
        # মায়া উত্তর দেওয়ার পর আবার টাইমার রিসেট
        last_activity_time = time.time()

    except Exception as e:
        bot.reply_to(message, "সোনা, আমার মাথায় একটু সমস্যা হচ্ছে গো!")

# রান করা
if __name__ == "__main__":
    init_db()
    print("মায়া এখন পুরোপুরি প্রস্তুত!")
    bot.infinity_polling()
            
