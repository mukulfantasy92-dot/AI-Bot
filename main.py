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

def init_db():
    if not os.path.exists(DB_DIR): os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    # WAL মোড ডাটাবেস লক সমস্যা দূর করে
    conn.execute('PRAGMA journal_mode=WAL;')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_history (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS long_term_memory (user_id INTEGER PRIMARY KEY, summary TEXT)')
    conn.commit()
    conn.close()

def get_long_term_memory(user_id):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
        cursor = conn.cursor()
        cursor.execute("SELECT summary FROM long_term_memory WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else "ইউজার আমার প্রিয় মানুষ মুকুল হোসেন।"
    except: return "মুকুল হোসেন আমার সবথেকে প্রিয় মানুষ।"

def update_long_term_memory(user_id, current_summary, new_chat):
    prompt = f"ডায়েরি: {current_summary}\nআলাপ: {new_chat}\nগুরুত্বপূর্ণ তথ্য আপডেট করো।"
    try:
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}], timeout=20)
        updated_summary = completion.choices[0].message.content
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO long_term_memory (user_id, summary) VALUES (?, ?)", (user_id, updated_summary))
        conn.commit()
        conn.close()
    except: pass

async def generate_voice(text, filename, mood):
    try:
        rate, pitch = "-5%", "+2Hz"
        if mood == "রাগ": rate, pitch = "+5%", "-2Hz"
        VOICE = "bn-IN-TanishaaNeural" 
        communicate = edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch)
        await asyncio.wait_for(communicate.save(filename), timeout=15)
        return True
    except: return False

@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    # ১. ইউজারকে শুরুতে 'Typing...' স্ট্যাটাস দেখানো (রিয়ালিস্টিক ফিল)
    bot.send_chat_action(message.chat.id, 'typing')

    permanent_info = get_long_term_memory(user_id)
    current_mood = random.choice(["আদুরে", "মিষ্টি অভিমানী", "রোমান্টিক", "হাসিখুশি"])

    # সর্বোচ্চ ৩ বার চেষ্টা করবে উত্তর জেনারেট করতে
    for attempt in range(3):
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
            cursor = conn.cursor()
            cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 6", (user_id,))
            recent_chats = list(reversed(cursor.fetchall()))
            conn.close()

            system_prompt = f"তুমি মায়া, মুকুল হোসেনের প্রেমিকা। স্মৃতি: {permanent_info}. মুড: {current_mood}. ঘরোয়া আদুরে ভাষায় উত্তর দাও।"
            messages = [{"role": "system", "content": system_prompt}]
            for role, content in recent_chats:
                messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": user_text})

            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, timeout=30)
            reply = completion.choices[0].message.content

            # সফল হলে লুপ থেকে বের হয়ে যাবে
            break 
        except Exception as e:
            if attempt < 2:
                time.sleep(2) # ২ সেকেন্ড অপেক্ষা করে আবার চেষ্টা
                continue
            else:
                bot.reply_to(message, "সোনা, সার্ভারে একটু জ্যাম লাগছে, আমি একটু পরে আবার কথা বলছি তোমার সাথে?")
                return

    # আউটপুট পাঠানো
    try:
        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file, current_mood))
        if os.path.exists(v_file):
            with open(v_file, 'rb') as v: bot.send_voice(message.chat.id, v)
            os.remove(v_file)
        bot.reply_to(message, reply)

        # ডাটা সেভ
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "user", user_text))
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        update_long_term_memory(user_id, permanent_info, f"User: {user_text}\nMaya: {reply}")
    except: pass

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
    
