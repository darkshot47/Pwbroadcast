import os
import json
import time
import threading
from datetime import datetime
import telebot
from telebot import types
from flask import Flask

# Configurations - Fetching from Environment Variables for Security
API_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_ID = int(os.getenv('ADMIN_ID', '123456789'))
USERS_DB = "users_db.json"

bot = telebot.TeleBot(API_TOKEN)

# Load/Save user data
def load_users():
    try:
        with open(USERS_DB, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    with open(USERS_DB, 'w') as f:
        json.dump(users, f, indent=4)

def is_admin(user_id):
    return user_id == ADMIN_ID

# Track broadcast state
broadcast_state = {}

# Dummy web server for Render port binding
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==================== START COMMAND ====================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    users = load_users()
    
    if user_id not in users:
        users[user_id] = {
            "name": message.from_user.first_name,
            "username": message.from_user.username,
            "joined_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "blocked": False
        }
        save_users(users)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎓 Browse Batches", url="https://t.me/SKY_XYR"))
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

# ==================== GET DATABASE BACKUP COMMAND ====================

@bot.message_handler(commands=['get_db'])
def send_db_file(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    try:
        with open(USERS_DB, "rb") as doc:
            bot.send_document(message.chat.id, doc, caption="📁 Active Users Database Backup")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error fetching DB: {e}")

# ==================== STATS COMMAND ====================

@bot.message_handler(commands=['stats'])
def show_stats(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    users = load_users()
    total_users = len(users)
    blocked_users = sum(1 for u in users.values() if u.get("blocked", False))
    active_users = total_users - blocked_users
    
    today = datetime.now().strftime("%Y-%m-%d")
    joined_today = sum(1 for u in users.values() if u.get("joined_date", "").startswith(today))
    
    stats_text = (
        "📊 **Bot Stats**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Active: {active_users}\n"
        f"🚫 Blocked: {blocked_users}\n"
        f"📈 Joined Today: {joined_today}\n\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# ==================== CANCEL COMMAND ====================

@bot.message_handler(commands=['cancel'])
def cancel_broadcast(message):
    if message.chat.id in broadcast_state:
        broadcast_state.pop(message.chat.id)
        bot.send_message(message.chat.id, "❌ Broadcast cancelled!")
    else:
        bot.send_message(message.chat.id, "No broadcast in progress!")

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
        "Send any message (text, photo, video, document) and I'll send it to all users.\n\n"
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
    
    chat_id = message.chat.id
    users = load_users()
    
    success, failed, blocked = 0, 0, 0
    status_msg = bot.send_message(chat_id, "📤 Broadcasting to users...")
    
    for user_id, user_data in users.items():
        if user_data.get("blocked", False):
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
            time.sleep(0.04)  # Rate limiting
        except Exception as e:
            if "blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                user_data["blocked"] = True
                blocked += 1
            else:
                failed += 1
    
    save_users(users)
    
    result_text = (
        f"✅ **Broadcast Complete!**\n\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}\n"
        f"🚫 Blocked: {blocked}\n"
        f"📊 Total: {len(users)}"
    )
    
    bot.edit_message_text(result_text, chat_id, status_msg.message_id, parse_mode='Markdown')
    broadcast_state.pop(chat_id, None)

# ==================== COMPLETE USER LISTS ====================

@bot.message_handler(commands=['user_list'])
def user_list(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    users = load_users()
    if not users:
        bot.send_message(message.chat.id, "❌ No users found!")
        return
    
    text = f"👥 **Total Users: {len(users)}**\n\n"
    
    for idx, (user_id, user_data) in enumerate(users.items(), 1):
        name = user_data.get("name", "Unknown")
        username = f" (@{user_data.get('username')})" if user_data.get("username") else ""
        entry = f"{idx}. {name}{username} - `{user_id}`\n"
        
        # Telegram character limit handling (4096 chars per message)
        if len(text) + len(entry) > 4000:
            bot.send_message(message.chat.id, text, parse_mode='Markdown')
            text = ""
            
        text += entry
    
    if text:
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['blocked_users'])
def blocked_users_list(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin only!")
        return
    
    users = load_users()
    blocked = {uid: data for uid, data in users.items() if data.get("blocked", False)}
    
    if not blocked:
        bot.send_message(message.chat.id, "✅ No blocked users!")
        return
    
    text = f"🚫 **Blocked Users: {len(blocked)}**\n\n"
    
    for idx, (user_id, user_data) in enumerate(blocked.items(), 1):
        name = user_data.get("name", "Unknown")
        entry = f"{idx}. {name} (`{user_id}`)\n"
        
        if len(text) + len(entry) > 4000:
            bot.send_message(message.chat.id, text, parse_mode='Markdown')
            text = ""
            
        text += entry
        
    if text:
        bot.send_message(message.chat.id, text, parse_mode='Markdown')

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    # Start Flask server in background thread for Render port binding
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Bot is running...")
    bot.infinity_polling()
                              
