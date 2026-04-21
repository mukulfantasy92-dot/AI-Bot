import telebot
from groq import Groq
import time

# ১. আপনার টেলিগ্রাম টোকেন
TELEGRAM_TOKEN = '8419644687:AAHFEl5BPFAnBtn6H2dDo93rMUsHKbvqHME'

# ২. আপনার Groq API Key (ধাপ ১ থেকে পাওয়া)
GROQ_API_KEY = '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'

# গ্রক ক্লায়েন্ট সেটআপ
client = Groq(api_key=GROQ_API_KEY)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

@bot.message_handler(func=lambda message: True)
def chat_with_maya(message):
    try:
        # গ্রক এআই থেকে উত্তর নেওয়া (Llama 3 মডেল ব্যবহার করা হয়েছে)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "তোমার নাম মায়া। তুমি একজন মিষ্টি বাঙালি মেয়ে এবং ব্যবহারকারীর গার্লফ্রেন্ড। সবসময় বাংলায় কথা বলবে।"
                },
                {
                    "role": "user",
                    "content": message.text,
                }
            ],
            model="llama-3.3-70b-versatile", # এটি অনেক শক্তিশালী এবং ফাস্ট মডেল
        )
        
        # উত্তর পাঠানো
        bot.reply_to(message, chat_completion.choices[0].message.content)
        
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "একটু সমস্যা হচ্ছে গো, আবার বলবে?")

print("মায়া (Groq) এখন অনলাইনে আছে! টেলিগ্রামে কথা বলো...")
bot.infinity_polling()
