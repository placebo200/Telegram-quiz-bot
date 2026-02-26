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
from oauth2client.service_account import ServiceAccountCredentials

# ==================== GOOGLE SHEET CONNECT ====================
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)
sheet = gc.open("Quiz").sheet1

QUESTION_LIMIT = 50

def load_data():
    data = sheet.get_all_records()
    random.shuffle(data)
    return data[:QUESTION_LIMIT]

# ==================== CONFIG ====================
ADMIN_ID = 1019767082
QUESTION_TIME = 25  # seconds per question

# ==================== STATE MANAGEMENT ====================
user_state = {}
leaderboard = {}
quiz_running = {}
current_poll_message = {}

# ==================== HELPER FUNCTIONS ====================
async def send_poll(chat_id, user_id, app):
    question_data = user_state[user_id]["data"][user_state[user_id]["index"]]
    question_text = question_data["Question"]
    options = [question_data[f"Option{i}"] for i in range(1, 5)]
    correct_index = int(question_data["Answer"]) - 1

    message = await app.bot.send_poll(
        chat_id=chat_id,
        question=question_text,
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_index,
        is_anonymous=False
    )
    current_poll_message[chat_id] = message.message_id

    async def timeout_next():
        await asyncio.sleep(QUESTION_TIME)
        if user_state.get(user_id) and user_state[user_id]["index"] < len(user_state[user_id]["data"]):
            await app.bot.send_message(chat_id, "⏱ Time up for this question!")
            user_state[user_id]["index"] += 1
            if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
                await send_poll(chat_id, user_id, app)
            else:
                score = user_state[user_id]["score"]
                leaderboard[user_id] = score
                duration = datetime.now() - user_state[user_id]["start_time"]
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}\nTime Taken: {duration.seconds} sec"
                )
                quiz_running[chat_id] = False

    asyncio.create_task(timeout_next())

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if quiz_running.get(chat_id):
        await update.message.reply_text("⚠️ Quiz already running!")
        return

    quiz_running[chat_id] = True
    user_state[user_id] = {
        "data": load_data(),
        "index": 0,
        "score": 0,
        "start_time": datetime.now()
    }
    await update.message.reply_text("🎉 Quiz started!")
    await send_poll(chat_id, user_id, context.application)

async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    user_id = answer.user.id
    chat_id = list(quiz_running.keys())[0]

    if user_id not in user_state:
        return

    question_index = user_state[user_id]["index"]
    question_data = user_state[user_id]["data"][question_index]
    correct_index = int(question_data["Answer"]) - 1

    if answer.option_ids[0] == correct_index:
        user_state[user_id]["score"] += 1

    user_state[user_id]["index"] += 1
    if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
        await send_poll(chat_id, user_id, context.application)
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
        global sheet
        sheet = gc.open("Quiz").sheet1
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