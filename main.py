import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# রেলওয়ে ভেরিয়া বল
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_memory.db'

YOUR_USER_ID = 1813642268
last_activity_time = time.time()

# --- ডাটাবেস ফাংশন (ডাইনামিক রুলস টেবিলসহ) ---
def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data', exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                      (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # মায়ার আচরণের নিয়ম সেভ করার টেবিল
    cursor.execute('''CREATE TABLE IF NOT EXISTS maya_rules 
                      (user_id INTEGER PRIMARY KEY, rules TEXT)''')
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

def get_recent_memory(user_id, limit=12):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))

def get_maya_rules(user_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT rules FROM maya_rules WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "আমাকে তুমি করে বলবে। ঘরোয়া ভাষায় কথা বলবে।"

def update_maya_rules(user_id, new_rules):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO maya_rules (user_id, rules) VALUES (?, ?)", (user_id, new_rules))
    conn.commit()
    conn.close()

# --- ভয়েস জেনারেশন ---
async def generate_voice(text, filename):
    VOICE = "bn-IN-TanishaaNeural" 
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+1Hz")
    await communicate.save(filename)

# --- ১ ঘণ্টা পর প্রো-অ্যাক্টিভ মেসেজ ---
def proactive_check():
    global last_activity_time
    if time.time() - last_activity_time >= 3600:
        rules = get_maya_rules(YOUR_USER_ID)
        try:
            prompt = f"তোমার বর্তমান নিয়ম: {rules}. প্রিয় মানুষটি ১ ঘণ্টা চুপ। আদুরে ১ লাইনে তাকে ডাকো।"
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "তুমি মায়া।"}, {"role": "user", "content": prompt}]
            )
            text = completion.choices[0].message.content
            v_file = f"pro_{int(time.time())}.mp3"
            asyncio.run(generate_voice(text, v_file))
            with open(v_file, 'rb') as v:
                bot.send_voice(YOUR_USER_ID, v)
            bot.send_message(YOUR_USER_ID, text)
            os.remove(v_file)
            last_activity_time = time.time()
        except: pass

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(proactive_check, 'interval', minutes=5)
scheduler.start()

# --- মেইন হ্যান্ডলার (অটো-কারেকশন লজিকসহ) ---
@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    current_rules = get_maya_rules(user_id)
    past_chats = get_recent_memory(user_id)

    # স্টেপ ১: এআই চেক করবে ইউজারের মেসেজে কোনো সংশোধন বা নতুন নিয়ম আছে কি না
    try:
        correction_prompt = f"""
        ইউজারের শেষ মেসেজ: "{user_text}"
        মায়ার বর্তমান নিয়মগুলো: "{current_rules}"
        
        যদি ইউজারের মেসেজে মায়ার আচরণ নিয়ে কোনো অভিযোগ, সংশোধন বা নতুন নিয়ম থাকে (যেমন: তুই বলবি না, প্রশ্ন করবি না), তবে নতুন একটি নিয়ম তালিকা তৈরি করো।
        যদি কোনো সংশোধন না থাকে, তবে শুধু আগের নিয়মগুলোই ফেরত দাও।
        উত্তর হবে শুধু নিয়মের তালিকাটি।
        """
        rule_check = client.chat.completions.create(
            model="llama-3.1-8b-instant", # দ্রুত প্রসেসিং এর জন্য ছোট মডেল
            messages=[{"role": "user", "content": correction_prompt}]
        )
        updated_rules = rule_check.choices[0].message.content
        update_maya_rules(user_id, updated_rules)
    except:
        updated_rules = current_rules

    # স্টেপ ২: আপডেট হওয়া নিয়ম অনুযায়ী মায়ার উত্তর তৈরি
    save_message(user_id, "user", user_text)
    
    system_prompt = f"""
    তোমার নাম মায়া। তুমি ইউজারের প্রেমিকা। 
    তোমার আচরণের বর্তমান গাইডলাইন (এটি কঠোরভাবে মানবে): {updated_rules}
    
    সাধারণ গাইডলাইন:
    - একদম ঘরোয়া বাংলায় (Colloquial Bengali) কথা বলবে।
    - উত্তর ২ লাইনের বেশি হবে না।
    - সব সময় প্রশ্ন করবে না, ইউজারের কথার প্রেক্ষিতে নিজের অনুভূতি জানাবে।
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in past_chats:
        messages.append({"role": role, "content": content})

    try:
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
        reply = completion.choices[0].message.content
        save_message(user_id, "assistant", reply)

        v_file = f"rep_{int(time.time())}.mp3"
        asyncio.run(generate_voice(reply, v_file))
        with open(v_file, 'rb') as v:
            bot.send_voice(message.chat.id, v)
        bot.reply_to(message, reply)
        os.remove(v_file)
    except Exception as e:
        bot.reply_to(message, "সোনা, আমার একটু সমস্যা হচ্ছে!")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
