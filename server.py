import uuid
import os
import asyncio
import uvicorn
import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8615060124:AAHlyzd6BT8kKkQ1l4pFws1QHMmM6AfGy88"

DATABASE_URL = "postgresql://postgres.cppomxileszfmujultra:anal12309876nfsj@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
# =============================================

app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        user_id BIGINT,
        username TEXT,
        hwid TEXT,
        activated INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    cursor.close()
    conn.close()

init_db()

class RegState(StatesGroup):
    waiting_for_nickname = State()

class VerifyRequest(BaseModel):
    key: str
    hwid: str

@app.post("/verify")
def verify_license(req: VerifyRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hwid, activated, username FROM keys WHERE key = %s", (req.key,))
    record = cursor.fetchone()
    
    if not record:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Invalid Key")

    saved_hwid, activated, username = record
    user_nick = username if username else "User"

    if activated == 0 or not saved_hwid:
        cursor.execute("UPDATE keys SET hwid = %s, activated = 1 WHERE key = %s", (req.hwid, req.key))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Key bound", "username": user_nick}

    if saved_hwid == req.hwid:
        cursor.close()
        conn.close()
        return {"status": "ok", "message": "Access granted", "username": user_nick}
    else:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=403, detail="HWID mismatch")

# --- ОБРАБОТЧИКИ TELEGRAM ---
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 **Добро пожаловать в систему KochVisual!**\n\n"
        "Чтобы зарегистрироваться и получить ключ, напиши команду /getkey",
        parse_mode="Markdown"
    )

@dp.message(Command("getkey"))
async def getkey_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, username FROM keys WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if row:
        await message.answer(
            f"⚠️ Ты уже зарегистрирован!\n"
            f"👤 Ник: **{row[1]}**\n"
            f"🔑 Ключ: `{row[0]}`",
            parse_mode="Markdown"
        )
        return

    await state.set_state(RegState.waiting_for_nickname)
    await message.answer("✍️ Напиши свой **никнейм**, который будет отображаться в клиенте:")

@dp.message(RegState.waiting_for_nickname, F.text)
async def process_nickname(message: types.Message, state: FSMContext):
    nick = message.text.strip()
    if len(nick) < 2 or len(nick) > 16:
        await message.answer("⚠️ Длина ника должна быть от 2 до 16 символов. Попробуй ещё раз:")
        return

    new_key = f"kochvisual-free-{uuid.uuid4().hex[:6]}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO keys (key, user_id, username, activated) VALUES (%s, %s, %s, 0)",
        (new_key, message.from_user.id, nick)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
    await state.clear()

    await message.answer(
        f"✅ **Регистрация завершена!**\n\n"
        f"👤 Твой ник: **{nick}**\n"
        f"🔑 Твой ключ: `{new_key}`\n\n"
        f"Введи этот ключ в игре при входе.",
        parse_mode="Markdown"
    )

async def main():
    config = uvicorn.Config(app=app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    print(f"[KochVisual] Сервер проверки запущен на порту {PORT}")
    await asyncio.gather(dp.start_polling(bot), server.serve())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("[KochVisual] Остановлен.")
