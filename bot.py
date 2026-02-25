import os
import random
import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PollAnswerHandler
)

# ===== CONFIG =====
SHEET_NAME = "Quiz"
QUESTION_LIMIT = 50
TIME_PER_QUESTION = 25
ADMIN_ID = 1019767082

# ===== GOOGLE SHEET CONNECT =====
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

def load_data():
    data = sheet.get_all_records()
    random.shuffle(data)
    return data[:QUESTION_LIMIT]

# ===== USER DATA =====
user_state = {}           # {user_id: {"index":0, "score":0, "data":[]}}
leaderboard = {}          # {user_id: score}
quiz_running = {}         # {chat_id: True/False}
current_poll_message = {} # {chat_id: poll_message_id}
quiz_task = {}            # {chat_id: asyncio.Task}
poll_data = {}            # {poll_id: {"user_id":..., "correct":...}}

# ===== SEND POLL =====
async def send_poll(update, context, user_id):
    chat_id = update.effective_chat.id
    if not quiz_running.get(chat_id, True):
        return

    q = user_state[user_id]["data"][user_state[user_id]["index"]]
    options = [q["A"], q["B"], q["C"], q["D"]]
    correct_index = ["A", "B", "C", "D"].index(q["Answer"])

    poll_msg = await context.bot.send_poll(
        chat_id=chat_id,
        question=q["Question"],
        options=options,
        type="quiz",
        correct_option_id=correct_index,
        is_anonymous=False
    )

    current_poll_message[chat_id] = poll_msg.message_id
    poll_data[poll_msg.poll.id] = {"user_id": user_id, "correct": correct_index}

    # Timer for next question
    task = asyncio.create_task(next_question_after_delay(update, context, user_id, TIME_PER_QUESTION))
    quiz_task[chat_id] = task

async def next_question_after_delay(update, context, user_id, delay):
    await asyncio.sleep(delay)
    await next_question(update, context, user_id)

# ===== START QUIZ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    quiz_running[chat_id] = True

    user_state[user_id] = {"index": 0, "score": 0, "data": load_data()}
    await send_poll(update, context, user_id)

# ===== POLL ANSWER =====
async def poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_id = update.poll_answer.poll_id
    user_id = update.poll_answer.user.id
    selected = update.poll_answer.option_ids[0]

    if poll_id not in poll_data:
        return  # Ignore if poll data missing

    correct = poll_data[poll_id]["correct"]
    if selected == correct:
        user_state[user_id]["score"] += 1

# ===== NEXT QUESTION =====
async def next_question(update, context, user_id):
    chat_id = update.effective_chat.id
    if not quiz_running.get(chat_id, True):
        return

    user_state[user_id]["index"] += 1
    if user_state[user_id]["index"] < len(user_state[user_id]["data"]):
        await send_poll(update, context, user_id)
    else:
        score = user_state[user_id]["score"]
        leaderboard[user_id] = score
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 Quiz Finished!\nYour Score: {score}/{QUESTION_LIMIT}"
        )

# ===== LEADERBOARD =====
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard:\n"
    for uid, score in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True):
        text += f"{uid} : {score}\n"
    await update.message.reply_text(text)# ===== ADMIN RELOAD =====
async def reload_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        global data
        data = load_data()
        await update.message.reply_text("✅ Sheet Reloaded")
    else:
        await update.message.reply_text("❌ Not Admin")

# ===== STOP QUIZ =====
async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    quiz_running[chat_id] = False

    if chat_id in quiz_task:
        quiz_task[chat_id].cancel()

    if chat_id in current_poll_message:
        await context.bot.stop_poll(chat_id, current_poll_message[chat_id])

    await update.message.reply_text("🛑 Quiz stopped")

# ===== MAIN =====
BOT_TOKEN = os.environ["BOT_TOKEN"]
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Command handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("stop", stop_quiz))
app.add_handler(CommandHandler("leaderboard", show_leaderboard))
app.add_handler(CommandHandler("reload", reload_sheet))
app.add_handler(PollAnswerHandler(poll_answer))

app.run_polling()