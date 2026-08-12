import os
import time
import threading
from datetime import datetime
import telebot
from telebot import types
from pymongo import MongoClient
from flask import Flask

# Configurations - Fetching from Environment Variables
API_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))
MONGO_URI = os.getenv('MONGO_URI')

bot = telebot.TeleBot(API_TOKEN)

# Initialize MongoDB Connection
if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client["telegram_bot_db"]
    users_col = db["users"]
else:
    users_col = None

def is_admin(user_id):
    return user_id == ADMIN_ID

broadcast_state = {}

# Flask app to bind Render's PORT requirement
app = Flask('')

@app.route('/')
def home():
    return "Bot Server Active with MongoDB!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==================== START COMMAND ====================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    
    user_data = {
        "_id": user_id,
        "name": message.from_user.first_name,
        "username": message.from_user.username,
        "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "blocked": False
    }
    
    # Save/Update user in MongoDB
    if users_col is not None:
        users_col.update_one({"_id": user_id}, {"$setOnInsert": user_data}, upsert=True)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎓 Browse Batches", url="t.me/FreestudytoolsAtoZ_bot/app"))
    markup.add(types.InlineKeyboardButton("👥 Refer & Earn", callback_data="refer"))
    
    bot.send_message(
        message.chat.id,
        "🎓 **Get FREE PW Batches Access!**\n\n"
        "✅ Premium courses\n"
        "✅ Live classes\n"
        "✅ Study materials\n\n"
        "Start learning now 👇",
        reply_markup=markup,
        parse_mode='Markdown'
    )

# ==================== STATS COMMAND ====================

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    if users_col is None:
        bot.send_message(message.chat.id, "❌ MongoDB connect nahi hai! Variable `MONGO_URI` set karein.")
        return

    total_users = users_col.count_documents({})
    blocked_users = users_col.count_documents({"blocked": True})
    active_users = total_users - blocked_users
    
    today = datetime.now().strftime("%Y-%m-%d")
    joined_today = users_col.count_documents({"joined_date": {"$regex": f"^{today}"}})
    
    stats_text = (
        "📊 **Bot Stats (MongoDB)**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Active: {active_users}\n"
        f"🚫 Blocked: {blocked_users}\n"
        f"📈 Joined Today: {joined_today}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# ==================== BROADCAST COMMAND ====================

@bot.message_handler(commands=['broadcast'])
def broadcast_init(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    broadcast_state[message.chat.id] = {"mode": "waiting"}
    
    bot.send_message(
        message.chat.id,
        "📢 **Broadcast Mode Active**\n\n"
        "Send any message and I'll send it to all users in MongoDB.\n\n"
        "Type `/cancel` to stop.",
        parse_mode='Markdown'
    )

@bot.message_handler(
    func=lambda msg: msg.chat.id in broadcast_state, 
    content_types=['text', 'photo', 'video', 'document', 'audio']
)
def handle_broadcast_content(message):
    if not is_admin(message.from_user.id):
        return
    
    if users_col is None:
        bot.send_message(message.chat.id, "❌ MongoDB connect nahi hai!")
        return

    chat_id = message.chat.id
    all_users = list(users_col.find())
    
    success, failed, blocked = 0, 0, 0
    status_msg = bot.send_message(chat_id, "📤 Broadcasting to all users...")
    
    for user in all_users:
        user_id = user["_id"]
        if user.get("blocked", False):
            blocked += 1
            continue
        
        try:
            if message.content_type == 'text':
                bot.send_message(int(user_id), message.text)
            elif message.content_type == 'photo':
                bot.send_photo(int(user_id), message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == 'video':
                bot.send_video(int(user_id), message.video.file_id, caption=message.caption)
            elif message.content_type == 'document':
                bot.send_document(int(user_id), message.document.file_id, caption=message.caption)
            elif message.content_type == 'audio':
                bot.send_audio(int(user_id), message.audio.file_id, caption=message.caption)
            
            success += 1
            time.sleep(0.04)
        except Exception as e:
            if "blocked" in str(e).lower() or "deactivated" in str(e).lower():
                users_col.update_one({"_id": user_id}, {"$set": {"blocked": True}})
                blocked += 1
            else:
                failed += 1
    
    result_text = (
        f"✅ **Broadcast Complete!**\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🚫 Blocked: {blocked}\n"
        f"📊 Total: {len(all_users)}"
    )
    
    bot.edit_message_text(result_text, chat_id, status_msg.message_id, parse_mode='Markdown')
    broadcast_state.pop(chat_id, None)

@bot.message_handler(commands=['cancel'])
def cancel_broadcast(message):
    if message.chat.id in broadcast_state:
        broadcast_state.pop(message.chat.id)
        bot.send_message(message.chat.id, "❌ Broadcast cancelled!")

# ==================== COMPLETE USER LIST ====================

@bot.message_handler(commands=['user_list'])
def user_list(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    if users_col is None:
        bot.send_message(message.chat.id, "❌ MongoDB connect nahi hai!")
        return

    all_users = list(users_col.find())
    if not all_users:
        bot.send_message(message.chat.id, "❌ Database me koi users nahi hain!")
        return
    
    text = f"👥 **Total Users: {len(all_users)}**\n\n"
    
    for idx, user in enumerate(all_users, 1):
        name = user.get("name", "Unknown")
        user_id = user["_id"]
        username = f" (@{user.get('username')})" if user.get("username") else ""
        entry = f"{idx}. {name}{username} - `{user_id}`\n"
        
        if len(text) + len(entry) > 4000:
            bot.send_message(message.chat.id, text, parse_mode='Markdown')
            text = ""
            
        text += entry
    
    if text:
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Bot is running with MongoDB Database...")
    bot.infinity_polling()
    
