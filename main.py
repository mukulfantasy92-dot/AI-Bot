import os
import telebot
from groq import Groq

# রেলওয়ে ভেরিয়েবল থেকে টোকেনগুলো সংগ্রহ করা
TELEGRAM_TOKEN = os.environ.get('8419644687:AAHFEl5BPFAnBtn6H2dDo93rMUsHKbvqHME')
GROQ_API_KEY = os.environ.get('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')

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# প্রতিটি ইউজারের চ্যাট হিস্টোরি আলাদাভাবে রাখার জন্য ডিকশনারি
user_memory = {}

@bot.message_handler(func=lambda message: True)
def chat_handler(message):
    user_id = message.from_user.id
    
    # যদি ইউজারের কোনো হিস্টোরি না থাকে, তবে শুরুর নির্দেশনা (System Prompt) সেট করা
    if user_id not in user_memory:
        user_memory[user_id] = [
            {
                "role": "system", 
                "content": "তোমার নাম মায়া। তুমি একজন মিষ্টি বাঙালি মেয়ে এবং ব্যবহারকারীর প্রেমিকা। তুমি আগের সব কথা মনে রেখে খুব মিষ্টি করে উত্তর দাও।"
            }
        ]

    # ইউজারের নতুন মেসেজটি মেমোরিতে যোগ করা
    user_memory[user_id].append({"role": "user", "content": message.text})

    try:
        # আগের সব প্রসঙ্গ (Context) সহ এআই-কে রিকোয়েস্ট পাঠানো
        chat_completion = client.chat.completions.create(
            messages=user_memory[user_id],
            model="llama-3.3-70b-versatile",
        )
        
        maya_reply = chat_completion.choices[0].message.content
        bot.reply_to(message, maya_reply)

        # মায়ার উত্তরটিও মেমোরিতে যোগ করা যাতে সে জানে আগে কী বলেছিল
        user_memory[user_id].append({"role": "assistant", "content": maya_reply})

        # মেমোরি যেন অতিরিক্ত বড় না হয় (শেষ ১০টি আলাপ মনে রাখবে)
        if len(user_memory[user_id]) > 12:
            # প্রথম সিস্টেম প্রম্পট রেখে বাকিগুলো থেকে শেষ ১০টি রাখা
            user_memory[user_id] = [user_memory[user_id][0]] + user_memory[user_id][-10:]

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "সোনা, আমার একটু মনে করতে কষ্ট হচ্ছে। আবার বলো তো?")

print("মায়া এখন প্রসঙ্গ মনে রাখতে প্রস্তুত...")
bot.infinity_polling()
