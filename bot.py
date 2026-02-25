import gspread
import random
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PollAnswerHandler, MessageHandler, filters

# ===== CONFIG =====
SHEET_NAME = "Quiz"
QUESTION_LIMIT = 50
TIME_PER_QUESTION = 30
ADMIN_ID = 1019767082

# ===== GOOGLE SHEET CONNECT =====
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

import os
import gspread
from google.oauth2.service_account import Credentials
import json

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(creds_dict)
gc = gspread.authorize(creds)
client = gspread.authorize(creds)
sheet = client.open("Quiz").sheet1

def load_data():
    data = sheet.get_all_records()
    random.shuffle(data)
    return data[:QUESTION_LIMIT]

data = load_data()

# ===== USER DATA =====
user_state = {}   # {user_id: {"index":0, "score":0, "data":[]}}
quiz_running = {}
quiz_task = {}
current_poll_message = {}
# ===== SEND QUESTION =====
async def send_poll(update, context, user_id):
    chat_id = update.effective_chat.id

    if not quiz_running.get(chat_id):
        return

    q = user_state[user_id]["data"][user_state[user_id]["index"]]
    options = [q["A"], q["B"], q["C"], q["D"]]
    correct_index = ["A","B","C","D"].index(q["Answer"])

    poll_msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=q["Question"],
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False
    )

    current_poll_message[chat_id] = poll_msg.message_id

async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    quiz_running[chat_id] = False

    if chat_id in quiz_task:
        quiz_task[chat_id].cancel()

    if chat_id in current_poll_message:
        await context.bot.stop_poll(chat_id, current_poll_message[chat_id])

    await update.message.reply_text("🛑 Quiz stopped")
# ===== START QUIZ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Agar pehle se quiz chal raha hai to band karo
    if chat_id in quiz_task:
        quiz_task[chat_id].cancel()

    quiz_running[chat_id] = True

    user_state[user_id] = {
        "index": 0,
        "score": 0,
        "data": load_data()
    }

    quiz_task[chat_id] = asyncio.create_task(run_quiz(update, context, user_id))
async def run_quiz(update, context, user_id):
    chat_id = update.effective_chat.id

    while quiz_running.get(chat_id):
        if user_state[user_id]["index"] >= len(user_state[user_id]["data"]):
            score = user_state[user_id]["score"]
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}"
            )
            quiz_running[chat_id] = False
            return

        await send_poll(update, context, user_id)
        await asyncio.sleep(TIME_PER_QUESTION)
        user_state[user_id]["index"] += 1
# ===== POLL ANSWER =====
async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = update.poll_answer.user.id
    selected = update.poll_answer.option_ids[0]

    if poll_id in context.chat_data:
        correct = context.chat_data[poll_id]["correct"]
        if selected == correct:
            user_state[user_id]["score"] += 1

# ===== NEXT QUESTION =====
async def next_question(update, context, user_id):
    chat_id = update.effective_chat.id

    if not quiz_running.get(chat_id):
        return
async def next_question(update, context, user_id):
    user_state[user_id]["index"] += 1
    if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
        await send_poll(update, context, user_id)
    else:
        score = user_state[user_id]["score"]
        leaderboard[user_id] = score
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}"
        )

# ===== LEADERBOARD =====
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard:\n"
    for uid, score in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True):
        text += f"{uid} : {score}\n"
    await update.message.reply_text(text)


# ===== ADMIN RELOAD =====
async def reload_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        global data
        data = load_data()
        await update.message.reply_text("✅ Sheet Reloaded")
    else:
        await update.message.reply_text("❌ Not Admin")
async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    quiz_running[chat_id] = False

    if chat_id in quiz_task:
        quiz_task[chat_id].cancel()

    if chat_id in current_poll_message:
        await context.bot.stop_poll(chat_id, current_poll_message[chat_id])

    await update.message.reply_text("🛑 Quiz stopped")
# ===== MAIN =====
import os
BOT_TOKEN = os.environ["BOT_TOKEN"]
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stop", stop_quiz))
app.add_handler(CommandHandler("leaderboard", show_leaderboard))
app.add_handler(CommandHandler("reload", reload_sheet))
app.add_handler(PollAnswerHandler(poll_answer))


app.run_polling()