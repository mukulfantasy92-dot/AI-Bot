import os
import telebot
from groq import Groq

# রেলওয়ে ভেরিয়েবল থেকে টোকেন নেওয়া
TELEGRAM_TOKEN = os.environ.get('8419644687:AAHFEl5BPFAnBtn6H2dDo93rMUsHKbvqHME')
GROQ_API_KEY = os.environ.get('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')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ইউজারদের মেসেজ হিস্টোরি জমানোর জন্য একটি ডিকশনারি
user_history = {}

@bot.message_handler(func=lambda message: True)
def maya_chat(message):
    user_id = message.from_user.id
    
    # যদি এই ইউজারের আগে কোনো হিস্টোরি না থাকে, তবে নতুন লিস্ট তৈরি হবে
    if user_id not in user_history:
        user_history[user_id] = [
            {"role": "system", "content": "তোমার নাম মায়া। তুমি একজন মিষ্টি বাঙালি মেয়ে এবং ব্যবহারকারীর প্রেমিকা। তুমি সবসময় আগের কথা মনে রেখে উত্তর দাও।"}
        ]

    # ইউজারের বর্তমান মেসেজটি মেমোরিতে যোগ করা
    user_history[user_id].append({"role": "user", "content": message.text})

    try:
        # আগের সব কথা (মেমোরি) সহ এআই-কে পাঠানো
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=user_history[user_id]
        )
        
        reply = completion.choices[0].message.content
        bot.reply_to(message, reply)

        # এআই-এর উত্তরটিও মেমোরিতে যোগ করা যাতে পরে মনে থাকে
        user_history[user_id].append({"role": "assistant", "content": reply})

        # মেমোরি যেন খুব বেশি বড় না হয়ে যায় (শেষ ১০টি কথা মনে রাখবে)
        if len(user_history[user_id]) > 10:
            user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    except Exception as e:
        print(f"Error: {e}")

bot.infinity_polling()
        print(f"Error: {e}")
        bot.reply_to(message, "একটু সমস্যা হচ্ছে গো, আবার বলবে?")

print("মায়া (Groq) এখন অনলাইনে আছে! টেলিগ্রামে কথা বলো...")
bot.infinity_polling()
