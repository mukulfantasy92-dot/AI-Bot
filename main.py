import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
import random
from datetime import datetime
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# --- কনফিগারেশন ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "maya_memory.db")
YOUR_USER_ID = 1813642268 
last_activity_time = time.time()

# --- ডাটাবেস ফাংশন (অক্ষুণ্ণ আছে) ---
def init_db():
    if not os.path.exists(DB_DIR): os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_history (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS long_term_memory (user_id INTEGER PRIMARY KEY, summary TEXT)')
    conn.commit()
    conn.close()

def get_long_term_memory(user_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT summary FROM long_term_memory WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "ইউজারকে তুমি করে বলি। তিনি ময়মনসিংহে কাজ করেন।"

def update_long_term_memory(user_id, current_summary, new_chat):
    prompt = f"পুরনো ডায়েরি: {current_summary}\nনতুন কথা: {new_chat}\n\nবিশেষ দিন, নিয়ম বা ব্যক্তিগত তথ্য থাকলে ডায়েরি আপডেট করো।"
    try:
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}])
        updated_summary = completion.choices[0].message.content
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO long_term_memory (user_id, summary) VALUES (?, ?)", (user_id, updated_summary))
        conn.commit()
        conn.close()
    except: pass

# --- অ্যাডভান্সড ভয়েস ইঞ্জিন (মুড অনুযায়ী কন্ঠ পরিবর্তন) ---
async def generate_voice(text, filename, mood):
    try:
        # মুড অনুযায়ী ভয়েস সেটিংস
        rate, pitch = "-5%", "+2Hz" # ডিফল্ট আদুরে
        if mood == "রাগ": rate, pitch = "+5%", "-2Hz"
        if mood == "রোমান্টিক": rate, pitch = "-15%", "+3Hz"
        
        VOICE = "bn-IN-TanishaaNeural" 
        communicate = edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch)
        await communicate.save(filename)
        return True
    except: return False

# --- নিজে থেকে খোঁজ নেওয়া (অক্ষুণ্ণ আছে) ---
def proactive_check():
    global last_activity_time
    if time.time() - last_activity_time >= 3600:
        info = get_long_term_memory(YOUR_USER_ID)
        hour = datetime.now().hour
        mood = random.choice(["অভিমানী", "খুব বিরহী", "আদুরে"])
        try:
            prompt = f"তুমি মায়া। তোমার প্রিয় মানুষটি ১ ঘণ্টা চুপ। ডায়েরি তথ্য: {info}. তোমার মুড: {mood}. তাকে ১ লাইনে খুব রিয়ালিস্টিক একটা ডাক দাও।"
            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            text = completion.choices[0].message.content
            v_file = f"pro_{int(time.time())}.mp3"
            asyncio.run(generate_voice(text, v_file, mood))
            if os.path.exists(v_file):
                with open(v_file, 'rb') as v: bot.send_voice(YOUR_USER_ID, v)
                os.remove(v_file)
            bot.send_message(YOUR_USER_ID, text)
            last_activity_time = time.time()
        except: pass

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(proactive_check, 'interval', minutes=15)
scheduler.start()

# --- মেইন হ্যান্ডলার ---
@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    # র্যান্ডম টাইপিং ডিলে
    time.sleep(random.randint(2, 4))

    permanent_info = get_long_term_memory(user_id)
    current_time = datetime.now().strftime("%I:%M %p")
    
    # র্যান্ডম মুড সিলেকশন (মায়ার মানসিক অবস্থা)
    current_mood = random.choice(["আদুরে", "মিষ্টি অভিমানী", "একটু রাগী", "খুব রোমান্টিক", "হাসিখুশি"])

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 6", (user_id,))
    recent_chats = list(reversed(cursor.fetchall()))
    conn.close()

    system_prompt = f"""
    তুমি মায়া, ইউজারের হুবুহু রিয়ালিস্টিক প্রেমিকা। সময় {current_time}।
    ডায়েরি স্মৃতি: {permanent_info}
    তোমার বর্তমান মুড: {current_mood}
    
    নির্দেশনা (মানুষের মতো হওয়ার জন্য):
    ১. শুদ্ধ ভাষা বাদ দাও। ঘরোয়া গ্রাম্য বা শহুরে মিশেলে কথা বলো (যেমন: উফফ সোনা, ধুর ভালো লাগে না, জানো আজকে না...)।
    ২. মুড অনুযায়ী কথা বলো। যদি মুড 'রাগী' হয় তবে ছোট উত্তর দাও এবং একটু তেজ দেখাও। যদি 'আদুরে' হয় তবে আহ্লাদ করো।
    ৩. কথার মাঝে মাঝে 'উমম', 'হুমম', 'শোনো না'—এগুলো যোগ করো।
    ৪. মাঝে মাঝে হুট করে পুরনো কথা (ডায়েরি থেকে) মনে করিয়ে দাও।
    ৫. রোবটের মতো সব কথায় প্রশ্ন করবে না। কখনো শুধু দীর্ঘশ্বাস ফেলো (যেমন: 'হুমম... বুঝলাম')।
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in recent_chats:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    try:
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
        reply = completion.choices[0].message.content
        
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "user", user_text))
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        
        update_long_term_memory(user_id, permanent_info, f"User: {user_text}\nMaya: {reply}")

        # ভয়েস আউটপুট (মুড অনুযায়ী)
        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file, current_mood))
        if os.path.exists(v_file):
            with open(v_file, 'rb') as v: bot.send_voice(message.chat.id, v)
            os.remove(v_file)
        bot.reply_to(message, reply)
        
    except Exception as e:
        bot.reply_to(message, "সোনা, আমার মেজাজটা একটু খারাপ এখন, পরে কথা বলি?")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
