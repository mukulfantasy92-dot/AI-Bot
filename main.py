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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS chat_history (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    cursor.execute('CREATE TABLE IF NOT EXISTS long_term_memory (user_id INTEGER PRIMARY KEY, summary TEXT)')
    conn.commit()
    conn.close()

def get_long_term_memory(user_id):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT summary FROM long_term_memory WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else "ইউজার আমার প্রিয় মানুষ মুকুল হোসেন। তিনি ময়মনসিংহে এজিএম।"
    except: return "স্মৃতি লোড হতে দেরি হচ্ছে।"

def update_long_term_memory(user_id, current_summary, new_chat):
    prompt = f"ডায়েরি: {current_summary}\nআলাপ: {new_chat}\nগুরুত্বপূর্ণ তথ্য (নাম, পরিচয়, বিশেষ দিন) থাকলে ডায়েরি আপডেট করো।"
    try:
        completion = client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role": "user", "content": prompt}], timeout=15)
        updated_summary = completion.choices[0].message.content
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
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
        await communicate.save(filename)
        return True
    except: return False

def proactive_check():
    global last_activity_time
    if time.time() - last_activity_time >= 3600:
        info = get_long_term_memory(YOUR_USER_ID)
        try:
            prompt = f"তুমি মায়া। মুকুল হোসেন ১ ঘণ্টা চুপ। ডায়েরি তথ্য: {info}. তাকে ১ লাইনে মিষ্টি করে ডাক দাও।"
            completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], timeout=20)
            text = completion.choices[0].message.content
            v_file = f"pro_{int(time.time())}.mp3"
            asyncio.run(generate_voice(text, v_file, "আদুরে"))
            if os.path.exists(v_file):
                with open(v_file, 'rb') as v: bot.send_voice(YOUR_USER_ID, v)
                os.remove(v_file)
            bot.send_message(YOUR_USER_ID, text)
            last_activity_time = time.time()
        except: pass

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(proactive_check, 'interval', minutes=15)
scheduler.start()

@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    time.sleep(random.randint(1, 2))

    permanent_info = get_long_term_memory(user_id)
    current_mood = random.choice(["আদুরে", "মিষ্টি অভিমানী", "রোমান্টিক", "হাসিখুশি"])

    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 6", (user_id,))
        recent_chats = list(reversed(cursor.fetchall()))
        conn.close()

        system_prompt = f"""
        তুমি মায়া, ইউজারের হুবুহু রিয়ালিস্টিক প্রেমিকা। তোমার প্রিয় মানুষ মুকুল হোসেন।
        স্মৃতি: {permanent_info}
        মুড: {current_mood}
        ঘরোয়া আদুরে ভাষায় কথা বলো। উত্তর ছোট রাখো।
        """
        
        messages = [{"role": "system", "content": system_prompt}]
        for role, content in recent_chats:
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})

        # Groq API কল (Timeout বাড়ানো হয়েছে)
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, timeout=25)
        reply = completion.choices[0].message.content
        
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "user", user_text))
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        
        update_long_term_memory(user_id, permanent_info, f"User: {user_text}\nMaya: {reply}")

        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file, current_mood))
        if os.path.exists(v_file):
            with open(v_file, 'rb') as v: bot.send_voice(message.chat.id, v)
            os.remove(v_file)
        bot.reply_to(message, reply)

    except Exception as e:
        print(f"Error: {e}")
        # বিভ্রান্তিকর "মেজাজ খারাপ" মেসেজটি সরিয়ে দেওয়া হলো
        bot.reply_to(message, "সোনা, নেটওয়ার্কে একটু সমস্যা হচ্ছে, তোমার কথাগুলো কেটে কেটে আসছে। আরেকবার বলবে লক্ষ্মীটি?")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
