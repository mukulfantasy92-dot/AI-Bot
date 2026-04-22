import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# --- কনফিগারেশন ও ভেরিয়েবল ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# রেলওয়ে ভলিউম পাথ (অবশ্যই /app/data মাউন্ট করা থাকতে হবে)
DB_DIR = "/app/data"
DB_PATH = os.path.join(DB_DIR, "maya_memory.db")
YOUR_USER_ID = 1813642268  # আপনার টেলিগ্রাম আইডি
last_activity_time = time.time()

# --- ডাটাবেস ফাংশন ---
def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    cursor = conn.cursor()
    # চ্যাট হিস্ট্রি টেবিল (সাম্প্রতিক কথা)
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                      (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # লং-টার্ম মেমোরি টেবিল (আজীবনের তথ্য ও নিয়ম)
    cursor.execute('''CREATE TABLE IF NOT EXISTS long_term_memory 
                      (user_id INTEGER PRIMARY KEY, summary TEXT)''')
    conn.commit()
    conn.close()

def get_long_term_memory(user_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT summary FROM long_term_memory WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "ইউজার সম্পর্কে এখনও বিশেষ কিছু জানি না। আমি তাকে তুমি করে সম্বোধন করি।"

def update_long_term_memory(user_id, current_summary, new_chat):
    """এআই প্রতিটি চ্যাট থেকে গুরুত্বপূর্ণ তথ্য বা নিয়ম খুঁজে বের করে ডায়েরিতে সেভ করবে"""
    prompt = f"""
    মায়ার বর্তমান স্থায়ী স্মৃতি ও নিয়মাবলী: "{current_summary}"
    নতুন কথোপকথন: "{new_chat}"
    
    কাজ:
    ১. যদি এই আলাপে ইউজার মায়াকে কোনো নতুন নিয়ম দেয় (যেমন: তুই বলবে না, প্রশ্ন কম করবে), তবে তা স্থায়ী স্মৃতিতে আপডেট করো।
    ২. যদি ইউজার নিজের ব্যক্তিগত তথ্য (পেশা, পরিবার, পছন্দ) দেয়, তবে তা যোগ করো।
    ৩. অপ্রয়োজনীয় কথা বাদ দিয়ে একটি ছোট ১-২ লাইনের সারাংশ তৈরি করো যা মায়াকে আজীবন মনে রাখতে হবে।
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        updated_summary = completion.choices[0].message.content
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO long_term_memory (user_id, summary) VALUES (?, ?)", (user_id, updated_summary))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Update Memory Error: {e}")

# --- ভয়েস জেনারেশন ---
async def generate_voice(text, filename):
    try:
        VOICE = "bn-IN-TanishaaNeural" 
        communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+1Hz")
        await communicate.save(filename)
        return True
    except: return False

# --- ১ ঘণ্টা পর নিজে থেকে খোঁজ নেওয়া (Proactive) ---
def proactive_check():
    global last_activity_time
    # ১ ঘণ্টা (৩৬০০ সেকেন্ড) চুপ থাকলে মায়া নিজে থেকে নক দিবে
    if time.time() - last_activity_time >= 3600:
        info = get_long_term_memory(YOUR_USER_ID)
        try:
            prompt = f"তুমি মায়া। তোমার প্রিয় মানুষটি ১ ঘণ্টা ধরে চুপ। তার সম্পর্কে তোমার ডায়েরি তথ্য: {info}. তাকে খুব আদুরে ১ লাইনে ডাকো বা খোঁজ নাও।"
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "তুমি মায়া। ঘরোয়া বাংলায় কথা বলো।"}, {"role": "user", "content": prompt}]
            )
            text = completion.choices[0].message.content
            v_file = f"pro_{int(time.time())}.mp3"
            asyncio.run(generate_voice(text, v_file))
            if os.path.exists(v_file):
                with open(v_file, 'rb') as v:
                    bot.send_voice(YOUR_USER_ID, v)
                os.remove(v_file)
            bot.send_message(YOUR_USER_ID, text)
            last_activity_time = time.time()
        except: pass

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(proactive_check, 'interval', minutes=10)
scheduler.start()

# --- মেসেজ হ্যান্ডলার ---
@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    # ১. স্থায়ী ও সাম্প্রতিক স্মৃতি লোড
    permanent_info = get_long_term_memory(user_id)
    
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT 8", (user_id,))
    recent_chats = list(reversed(cursor.fetchall()))
    conn.close()

    # ২. সিস্টেম প্রম্পট (মায়ার ব্যক্তিত্ব)
    system_prompt = f"""
    তোমার নাম মায়া। তুমি ইউজারের প্রেমিকা। 
    তোমার ডায়েরিতে লেখা স্থায়ী তথ্য ও নিয়ম: {permanent_info}
    
    নির্দেশনা:
    - একদম ঘরোয়া বাংলায় কথা বলো (যেমন: করছো গো, খেয়েছো তুমি?, হুমম, পাগল)।
    - ইউজার যদি তোমাকে কোনো নিয়ম শিখিয়ে দেয় (যেমন: তুই বলবি না), তবে পরের মেসেজ থেকেই তা মেনে চলো।
    - সব সময় প্রশ্ন করবে না, মাঝে মাঝে শুধু উত্তর দাও বা নিজের ভালো লাগার কথা বলো।
    - উত্তর খুব ছোট ও রিয়ালিস্টিক (১-২ লাইন) রাখবে।
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in recent_chats:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

    try:
        # ৩. রিপ্লাই তৈরি
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
        reply = completion.choices[0].message.content
        
        # ৪. ডাটা সেভ ও ডাইনামিক লার্নিং
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "user", user_text))
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, "assistant", reply))
        conn.commit()
        conn.close()
        
        # ব্যাকগ্রাউন্ডে ডায়েরি আপডেট
        update_long_term_memory(user_id, permanent_info, f"User: {user_text}\nMaya: {reply}")

        # ৫. ভয়েস ও আউটপুট
        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file))
        if os.path.exists(v_file):
            with open(v_file, 'rb') as v:
                bot.send_voice(message.chat.id, v)
            os.remove(v_file)
        bot.reply_to(message, reply)
        
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "সোনা, আমার একটু সমস্যা হচ্ছে গো!")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
