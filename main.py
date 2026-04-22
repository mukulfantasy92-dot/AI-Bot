import os
import telebot
import sqlite3
import asyncio
import edge_tts
import time
from groq import Groq
from apscheduler.schedulers.background import BackgroundScheduler

# ভেরিয়েবল সেটআপ
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)
DB_PATH = '/app/data/maya_memory.db'

YOUR_USER_ID = 1813642268
last_activity_time = time.time()

def init_db():
    if not os.path.exists('/app/data'):
        os.makedirs('/app/data', exist_ok=True)
    # timeout যোগ করা হয়েছে যাতে ডাটাবেস লক না হয়
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                      (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS maya_rules 
                      (user_id INTEGER PRIMARY KEY, rules TEXT)''')
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Save Error: {e}")

def get_recent_memory(user_id, limit=10):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return list(reversed(rows))
    except:
        return []

def get_maya_rules(user_id):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT rules FROM maya_rules WHERE user_id=?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else "আমাকে তুমি করে বলবে। ঘরোয়া ভাষায় কথা বলবে।"
    except:
        return "ঘরোয়া ভাষায় কথা বলো।"

def update_maya_rules(user_id, new_rules):
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO maya_rules (user_id, rules) VALUES (?, ?)", (user_id, new_rules))
        conn.commit()
        conn.close()
    except: pass

async def generate_voice(text, filename):
    try:
        VOICE = "bn-IN-TanishaaNeural" 
        communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+1Hz")
        await communicate.save(filename)
        return True
    except:
        return False

@bot.message_handler(func=lambda message: True)
def handle_maya(message):
    global last_activity_time
    user_id = message.from_user.id
    user_text = message.text
    last_activity_time = time.time()

    current_rules = get_maya_rules(user_id)
    past_chats = get_recent_memory(user_id)

    # ডাইনামিক রুল চেক
    try:
        correction_prompt = f"ইউজারের শেষ মেসেজ: '{user_text}'. আগের নিয়ম: '{current_rules}'. যদি কোনো নতুন নিয়ম বা সংশোধন থাকে তবে শুধু নতুন নিয়মের তালিকা দাও, নয়তো আগেরটাই দাও।"
        rule_check = client.chat.completions.create(
            model="llama-3.1-8b-instant", # দ্রুত প্রসেসিং
            messages=[{"role": "user", "content": correction_prompt}]
        )
        updated_rules = rule_check.choices[0].message.content
        update_maya_rules(user_id, updated_rules)
    except:
        updated_rules = current_rules

    save_message(user_id, "user", user_text)
    
    system_prompt = f"তোমার নাম মায়া। তুমি ইউজারের প্রেমিকা। তোমার নিয়ম: {updated_rules}. একদম ঘরোয়া ভাষায় ১-২ লাইনে উত্তর দাও।"
    
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
        # এভরিথিং ওকে থাকলে ভয়েস জেনারেট হবে
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(generate_voice(reply, v_file))

        if success and os.path.exists(v_file):
            with open(v_file, 'rb') as v:
                bot.send_voice(message.chat.id, v)
            os.remove(v_file)
        
        bot.reply_to(message, reply)
        
    except Exception as e:
        print(f"Error in main handler: {e}")
        bot.reply_to(message, "সোনা, আমার একটু মাথা ধরেছে গো! একটু পরে কথা বলি?")

if __name__ == "__main__":
    init_db()
    bot.infinity_polling()
