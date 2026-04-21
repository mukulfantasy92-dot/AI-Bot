import telebot
from groq import Groq

# এখানে আপনার টোকেন ও কি সরাসরি লিখে দিন (শুধুমাত্র Pydroid-এ টেস্টের জন্য)
TELEGRAM_TOKEN = '8419644687:AAHFEl5BPFAnBtn6H2dDo93rMUsHKbvqHME'
GROQ_API_KEY = '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' 

client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# মেমোরি জমানোর ডিকশনারি
user_history = {}

@bot.message_handler(func=lambda message: True)
def maya_chat(message):
    user_id = message.from_user.id
    
    if user_id not in user_history:
        user_history[user_id] = [
            {"role": "system", "content": "তোমার নাম মায়া। তুমি একজন মিষ্টি বাঙালি মেয়ে। তুমি আগের কথা মনে রেখে উত্তর দাও।"}
        ]

    user_history[user_id].append({"role": "user", "content": message.text})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=user_history[user_id]
        )
        
        reply = completion.choices[0].message.content
        bot.reply_to(message, reply)
        user_history[user_id].append({"role": "assistant", "content": reply})

        # মেমোরি লিমিট (শেষ ১০টি মেসেজ)
        if len(user_history[user_id]) > 10:
            user_history[user_id] = [user_history[user_id][0]] + user_history[user_id][-10:]

    except Exception as e:
        print(f"Error: {e}")

print("মায়া এখন মেমোরিসহ অনলাইনে আছে...")
bot.infinity_polling()
