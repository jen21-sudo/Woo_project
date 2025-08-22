import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from googleapiclient.discovery import build
from groq import Groq
from jinja2 import Template

# === 🔑 API Keys (replace with your real keys) ===
YOUTUBE_API_KEY = "AIzaSyDNrN-efsei0J6hHU-9uSEcS0QblaUtHjQ"
GROQ_API_KEY = "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"

# === 📧 SMTP Configuration for Parent Reports ===
EMAIL_ADDRESS = "jeanrakn@gmail.com"      # ← Replace with your Gmail
EMAIL_PASSWORD = "gadm kbqu ltbq cyjf"    # ← App password (https://myaccount.google.com/apppasswords)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# === 🎯 API Services ===
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
GROQ_MODEL = "llama3-8b-8192"

# === 📁 Files & Initial Data ===
USER_PREFERENCES_FILE = "user_preferences.json"
INITIAL_CATEGORIES = ["Drawing", "Tutorials", "Crafts", "Challenges", "Painting", "Favorites"]

INITIAL_VIDEOS_BY_CATEGORY = {
    "Drawing": [
        {"id": "rTgj1HxmUeg", "title": "Learn to draw a lion!"},
        {"id": "v91oQN9y7dQ", "title": "Easy drawing: a cute dog"},
        {"id": "Z5O8d9YVq9k", "title": "Drawing tutorial for kids"}
    ],
    "Tutorials": [
        {"id": "dQw4w9WgXcQ", "title": "How to tie shoelaces"},
        {"id": "XsT6rhvUuCA", "title": "Paper folding tutorial"}
    ],
    "Crafts": [
        {"id": "mQW6y4YcZ8c", "title": "Easy craft with cardboard"},
        {"id": "JkYXZxYxN2w", "title": "Build your robot from boxes"}
    ],
    "Challenges": [
        {"id": "LXb3E3B8SdI", "title": "The 10-second challenge!"},
        {"id": "pRpeEdMmmQ0", "title": "Funny challenge: jump without laughing"}
    ],
    "Painting": [
        {"id": "kXZER8V1VvI", "title": "Finger painting"},
        {"id": "FUSn1YP2qpk", "title": "Create a rainbow with paint"}
    ],
    "Favorites": []
}

# === 🛠️ Initialize Database ===
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            child_name TEXT,
            child_age INTEGER,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS viewed_videos (
            user_id TEXT,
            video_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, video_id)
        )
    """)
    conn.commit()
    conn.close()

def calculate_distance(pos1, pos2):
    return abs(pos1['h'] - pos2['h']) + abs(pos1['v'] - pos2['v'])

def minimax(position, target, depth, is_maximizing_player):
    if position == target:
        return 1, []  # AI wins
    if depth == 0:
        return -calculate_distance(position, target), []  # Heuristic

    possible_moves = ['right', 'left', 'up', 'down']
    best_score = float('-inf') if is_maximizing_player else float('inf')
    best_path = []

    for move in possible_moves:
        new_pos = position.copy()
        if move == 'right': new_pos['h'] += 1
        if move == 'left': new_pos['h'] -= 1
        if move == 'up': new_pos['v'] -= 1
        if move == 'down': new_pos['v'] += 1

        score, path = minimax(new_pos, target, depth - 1, not is_maximizing_player)
        if (is_maximizing_player and score > best_score) or (not is_maximizing_player and score < best_score):
            best_score = score
            best_path = [move] + path

    return best_score, best_path

# === 🤖 Async AI Response via Groq ===
async def get_ai_response(prompt: str) -> str:
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a friendly science guide for children. Always answer in simple English. Just explain in a way kids understand. Don't add any formatting like titles. Just return the answer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting application: Initializing database...")
    init_db()
    yield
    print("🛑 Shutting down application.")

app = FastAPI(lifespan=lifespan)

# === 👤 User Session with Activity Tracking ===
class UserSession:
    def __init__(self, user_id: str, websocket: WebSocket):
        self.user_id = user_id
        self.websocket = websocket
        self.is_authenticated = True
        self.child_name = None
        self.avatar = None
        self.parent_email = None
        self.start_time = datetime.now()

        # 🔹 Activity tracking for report
        self.messages = []
        self.videos_viewed = []
        self.categories_explored = set()

active_connections: list[UserSession] = []

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_viewed_video_ids(user_id: str) -> list:
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT video_id FROM viewed_videos WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def add_viewed_video(user_id: str, video_id: str):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO viewed_videos (user_id, video_id) VALUES (?, ?)", (user_id, video_id))
        conn.commit()
    except Exception as e:
        print(f"❌ Error saving viewed video: {e}")
    finally:
        conn.close()

async def generate_ai_response_structured(prompt: str) -> dict:
    """Generates a structured JSON response from AI."""
    try:
        client = Groq(api_key=GROQ_API_KEY)
        system_prompt = """
        You assist a child. For each request, return a strict JSON with two keys:
        1. "ai_message": A short, kind message for the child.
        2. "search_query": A concise query to search YouTube videos.

        Example:
        {
          "ai_message": "I'll find great cat videos for you!",
          "search_query": "funny cat videos for kids"
        }
        """
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.7
        )
        return json.loads(chat_completion.choices[0].message.content)
    except Exception as e:
        print(f"❌ AI error: {e}")
        return {
            "ai_message": "I couldn't generate a response right now. Can you rephrase?",
            "search_query": ""
        }

async def search_videos(query: str, user_id: str) -> list:
    """Search YouTube videos (simplified)."""
    try:
        youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)
        response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=10,
            safeSearch="strict",
            type="video",
            regionCode="FR"
        ).execute()

        viewed_ids = set(get_viewed_video_ids(user_id))
        results = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            if video_id not in viewed_ids:
                results.append({
                    "id": video_id,
                    "title": item["snippet"]["title"]
                })
                if len(results) >= 10:
                    break
        return results
    except Exception as e:
        print(f"❌ YouTube search error: {e}")
        return []

# === 📧 Generate and Send Parent Report ===
async def generate_activity_summary(session: UserSession) -> str:
    """Ask AI to summarize child's activity."""
    try:
        prompt = f"""
        You are a kind educator. Here is {session.child_name}'s activity:
        - Messages sent: {', '.join([m['text'][:30] + '...' for m in session.messages[-5:]])}
        - Videos watched: {len(session.videos_viewed)}
        - Categories explored: {', '.join(session.categories_explored)}
        - Duration: {datetime.now() - session.start_time}

        Write a warm, positive, educational summary (3-4 sentences) for parents.
        Highlight curiosity, creativity, or learning.
        """
        response = await generate_ai_response_structured(prompt)
        return response.get('ai_message', "Your child explored several topics with interest.")
    except Exception as e:
        return "Your child explored several topics with interest."

async def send_parent_report(session: UserSession):
    """Send an email report to the parent."""
    if not session.parent_email:
        print("❌ No parent email defined.")
        return

    duration = datetime.now() - session.start_time
    summary = await generate_activity_summary(session)

    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 700px; margin: auto; padding: 20px;">
        <h2>📊 Activity Report - {session.child_name}</h2>
        <p>Hello!</p>
        <p>Your child used <strong>WOO</strong> for <strong>{str(duration).split('.')[0]}</strong>.</p>

        <h3>📝 Messages Sent</h3>
        <ul>
        {''.join(f'<li><em>{m["text"]}</em> ({m["timestamp"][:16]})</li>' for m in session.messages[-10:])}
        </ul>

        <h3>🎬 Videos Watched ({len(session.videos_viewed)})</h3>
        <ul>
        {''.join(f'<li>{v["title"]}</li>' for v in session.videos_viewed[:5])}
        {f'<li>... and {len(session.videos_viewed) - 5} others</li>' if len(session.videos_viewed) > 5 else ''}
        </ul>

        <h3>🔍 Categories Explored</h3>
        <p>{', '.join(session.categories_explored) or 'None'}</p>

        <h3>🧠 AI Summary</h3>
        <p style="background-color: #f0f8ff; padding: 10px; border-radius: 5px; font-style: italic;">
            {summary}
        </p>

        <hr>
        <p><small>This report was automatically generated by WOO. Do not reply to this email.</small></p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"👶 {session.child_name}'s Activity on WOO"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = session.parent_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=EMAIL_ADDRESS,
            password=EMAIL_PASSWORD,
            start_tls=True
        )
        print(f"✅ Report sent to {session.parent_email}")
    except Exception as e:
        print(f"❌ Failed to send report: {e}")

# === 🌐 WebSocket Endpoint ===
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_session = None

    # Send categories
    await websocket.send_text(json.dumps({"type": "categories", "categories": INITIAL_CATEGORIES}))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            print("📩 Received message:", message)

            # === 🔐 Register ===
            if message["type"] == "register":
                email = message["email"]
                password = message["password"]
                child_name = message["child_name"]
                child_age = message["child_age"]
                avatar = message["avatar"]
                password_hash = hash_password(password)
                user_id = str(uuid.uuid4())

                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                        INSERT INTO users (user_id, email, password_hash, child_name, child_age, avatar)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, email, password_hash, child_name, child_age, avatar))
                    conn.commit()

                    user_session = UserSession(user_id, websocket)
                    user_session.child_name = child_name
                    user_session.avatar = avatar
                    user_session.parent_email = email
                    active_connections.append(user_session)

                    await websocket.send_text(json.dumps({
                        "type": "auth_success",
                        "userId": user_id,
                        "child_name": child_name,
                        "avatar": avatar,
                        "email": email
                    }))
                except sqlite3.IntegrityError:
                    await websocket.send_text(json.dumps({
                        "type": "auth_error",
                        "message": "This email is already in use."
                    }))
                finally:
                    conn.close()

            # === 🔐 Login ===
            elif message["type"] == "login":
                email = message["email"]
                password = message["password"]
                password_hash = hash_password(password)

                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, avatar, child_name FROM users WHERE email = ? AND password_hash = ?", (email, password_hash))
                row = cursor.fetchone()
                conn.close()

                if row:
                    user_id, avatar, child_name = row
                    user_session = UserSession(user_id, websocket)
                    user_session.child_name = child_name
                    user_session.avatar = avatar
                    user_session.parent_email = email
                    active_connections.append(user_session)

                    await websocket.send_text(json.dumps({
                        "type": "auth_success",
                        "userId": user_id,
                        "child_name": child_name,
                        "avatar": avatar,
                        "email": email
                    }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "auth_error",
                        "message": "Incorrect email or password."
                    }))

            # === 📝 Child's Query ===
            elif message["type"] == "query":
                user_id = message.get("user_id")
                text = message.get("text", "").strip()
                if not user_id or not text: continue

                for s in active_connections:
                    if s.user_id == user_id:
                        s.messages.append({"text": text, "timestamp": datetime.now().isoformat()})
                        break

                ai_response = await generate_ai_response_structured(text)
                ai_message = ai_response.get("ai_message")
                search_query = ai_response.get("search_query")

                videos = await search_videos(search_query, user_id)

                await websocket.send_text(json.dumps({
                    "type": "videos",
                    "message": ai_message,
                    "videos": videos
                }))

            # === 📚 Category Selected ===
            elif message["type"] == "category_query":
                category = message.get("text", "").strip()
                user_id = message.get("user_id")
                if not category: continue

                for s in active_connections:
                    if s.user_id == user_id:
                        s.categories_explored.add(category)
                        break

                ai_response = await generate_ai_response_structured(f"Find videos about {category} for kids.")
                ai_message = ai_response.get("ai_message")
                search_query = ai_response.get("search_query")

                videos = await search_videos(search_query, user_id)

                await websocket.send_text(json.dumps({
                    "type": "videos",
                    "message": ai_message,
                    "videos": videos
                }))

            # === 🎥 Video Watched ===
            elif message["type"] == "video_viewed":
                video_id = message.get("video_id")
                video_title = message.get("video_title")
                user_id = message.get("user_id")
                if video_id and user_id:
                    add_viewed_video(user_id, video_id)
                    for s in active_connections:
                        if s.user_id == user_id:
                            s.videos_viewed.append({
                                "id": video_id,
                                "title": video_title,
                                "timestamp": datetime.now().isoformat()
                            })
                            break

            # === ❓ Get Questions by Theme ===
            elif message['type'] == "get_questions":
                theme = message.get("theme")
                print(f"Received request for theme: {theme}")

                prompt = f"""
                Act as a science guide for children aged 6-10.
                Generate 4 simple and fun curiosity questions about {theme}.
                Do not include answers.
                Write each question on a new line.
                Answer in English.
                """
                ai_text = await get_ai_response(prompt)
                questions = [q.strip() for q in ai_text.split('\n') if q.strip()]
                await websocket.send_json({"type": "questions", "questions": questions})
                print("Questions sent to client.")

            # === 💡 Get Answer to Question ===
            elif message['type'] == "get_reponse":
                question = message.get("question")
                print(f"Received request for question: {question}")

                prompt = f"""
                Explain the answer to '{question}' for a child aged 6-10.
                Use simple words and fun analogies.
                Keep it under 3 sentences.
                Answer in English.
                """
                ai_text = await get_ai_response(prompt)
                await websocket.send_json({"type": "reponse", "reponse": ai_text})
                print("Answer sent to client.")

            # === 🤖 AI Turn in Game ===
            elif message.get("turn") == "ai":
                player_pos = message['playerPos']
                target_pos = message['targetPos']
                path = []
                h, v = player_pos['h'], player_pos['v']

                while h < target_pos['h']:
                    path.append('right')
                    h += 1
                while h > target_pos['h']:
                    path.append('left')
                    h -= 1
                while v < target_pos['v']:
                    path.append('down')
                    v += 1
                while v > target_pos['v']:
                    path.append('up')
                    v -= 1

                await websocket.send_text(json.dumps({"aiPath": path}))

            # === 🧱 Block Logic ===
            elif message.get("blocks") is not None:
                blocks = message.get("blocks")
                print(f"Received blocks: {blocks}")
                system_prompt = (
                    "You are an AI assistant for a coding game. "
                    "The user gives a list of movement blocks: 'right', 'left', 'up', 'down'. "
                    "Calculate the final (h, v) position starting from (0,0). "
                    "Generate a formula like 'right + right - up = (2, -1)'. "
                    "Then suggest a fun new goal as a JSON with 'goal', 'formula', and 'result'."
                )
                user_prompt = f"Blocks: {blocks}"
                try:
                    client = Groq(api_key=GROQ_API_KEY)
                    completion = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=100,
                        response_format={"type": "json_object"}
                    )
                    ai_response = completion.choices[0].message.content.strip()
                    await websocket.send_text(ai_response)
                except Exception as e:
                    print(f"Groq API error: {e}")
                    await websocket.send_text(json.dumps({"error": "Failed to get goal from AI."}))

            else:
                await websocket.send_text(json.dumps({"error": "Invalid data received."}))

    except WebSocketDisconnect:
        if user_session and user_session in active_connections:
            await send_parent_report(user_session)
            active_connections.remove(user_session)
        print("🔌 Client disconnected.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if user_session and user_session in active_connections:
            active_connections.remove(user_session)