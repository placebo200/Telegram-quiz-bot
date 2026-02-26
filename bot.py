# ==================== TELEGRAM QUIZ BOT ====================
import os
import json
import random
import asyncio
from datetime import datetime
from telegram import Update, Poll
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    PollAnswerHandler,
    ContextTypes
)
import gspread
from google.oauth2.service_account import Credentials

# ==================== GOOGLE SHEET CONNECT ====================
import os
import json
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets / Drive scope
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Render / Environment variable se creds load karna
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

# gspread authorize
gc = gspread.authorize(creds)
sheet = gc.open("Quiz").sheet1  # Yahan "Quiz" tumhare sheet ka naam hai

# Question load function
QUESTION_LIMIT = 50
def load_data():
    data = sheet.get_all_records()
    random.shuffle(data)
    return data[:QUESTION_LIMIT]

# Quiz data ready
data = load_data()
# ==================== CONFIG ====================
QUESTION_LIMIT = 50
ADMIN_ID = 1019767082
QUESTION_TIME = 25

# ==================== DATA LOAD ====================
def load_data():
    data = sheet.get_all_records()
    random.shuffle(data)
    return data[:QUESTION_LIMIT]

# ==================== STATE MANAGEMENT ====================
user_state = {}             # Tracks quiz index, score, start_time per user
leaderboard = {}            # Tracks final scores
quiz_running = {}           # Tracks if quiz is running per chat
current_poll_message = {}   # Current poll message ID per chat

# ==================== HELPER FUNCTIONS ====================
async def send_poll(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    question_data = user_state[user_id]["data"][user_state[user_id]["index"]]
    question_text = question_data["Question"]
    options = [question_data[f"Option{i}"] for i in range(1, 5)]
    correct_index = int(question_data["Answer"]) - 1

    message = await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=question_text,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        is_anonymous=False
    )
    current_poll_message[update.effective_chat.id] = message.message_id

    # start timeout for the question
    async def timeout_next():
        await asyncio.sleep(QUESTION_TIME)
        # check if user is still on the same question
        if user_state.get(user_id) and user_state[user_id]["index"] < len(user_state[user_id]["data"]):
            await context.bot.send_message(update.effective_chat.id, "⏱ Time up for this question!")
            user_state[user_id]["index"] += 1
            if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
                await send_poll(update, context, user_id)
            else:
                score = user_state[user_id]["score"]
                leaderboard[user_id] = score
                duration = datetime.now() - user_state[user_id]["start_time"]
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}\nTime Taken: {duration.seconds} sec"
                )
                quiz_running[update.effective_chat.id] = False

    asyncio.create_task(timeout_next())

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if quiz_running.get(chat_id):
        await update.message.reply_text("⚠️ Quiz already running!")
        return

    quiz_running[chat_id] = True
    user_state[update.effective_user.id] = {
        "data": load_data(),
        "index": 0,
        "score": 0,
        "start_time": datetime.now()
    }
    await update.message.reply_text("🎉 Quiz started!")
    await send_poll(update, context, update.effective_user.id)

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id
    chat_id = update.effective_chat.id if update.effective_chat else list(quiz_running.keys())[0]

    if user_id not in user_state:
        returnquestion_index = user_state[user_id]["index"]
    question_data = user_state[user_id]["data"][question_index]
    correct_index = int(question_data["Answer"]) - 1

    if answer.option_ids[0] == correct_index:
        user_state[user_id]["score"] += 1

    # Move to next question
    user_state[user_id]["index"] += 1
    if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
        await send_poll(update, context, user_id)
    else:
        score = user_state[user_id]["score"]
        leaderboard[user_id] = score
        duration = datetime.now() - user_state[user_id]["start_time"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}\nTime Taken: {duration.seconds} sec"
        )
        quiz_running[chat_id] = False

async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    quiz_running[chat_id] = False
    await update.message.reply_text("🛑 Quiz stopped")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard:\n"
    for uid, score in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True):
        text += f"{uid} : {score}\n"
    await update.message.reply_text(text)

async def reload_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        global data
        data = load_data()
        await update.message.reply_text("✅ Sheet Reloaded")
    else:
        await update.message.reply_text("❌ Not Admin")

# ==================== MAIN ====================
BOT_TOKEN = os.environ["BOT_TOKEN"]
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stop", stop_quiz))
app.add_handler(CommandHandler("leaderboard", show_leaderboard))
app.add_handler(CommandHandler("reload", reload_sheet))
app.add_handler(PollAnswerHandler(poll_answer))

print("🤖 Bot is running...")
app.run_polling()