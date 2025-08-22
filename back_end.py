from openai import OpenAI
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
from jinja2 import Template

# === 🔑 Clés API ===
AIML_API_KEY = "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"  # ← Remplace par ta vraie clé
YOUTUBE_API_KEY = "AIzaSyCqK4vF3H-gHBdMuSVUtSNI1KXhWvS159Q"

# === 📧 Configuration SMTP pour les rapports aux parents ===
EMAIL_ADDRESS = "jeanrakn@gmail.com"
EMAIL_PASSWORD = "gadm kbqu ltbq cyjf"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# === 🎯 Services API ===
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
LLM_MODEL = "gpt-4o"  # Modèle disponible sur aimlapi

# === 📁 Fichiers & données initiales ===
USER_PREFERENCES_FILE = "user_preferences.json"
INITIAL_CATEGORIES = ["Dessin", "Tutoriels", "Bricolage", "Challenges", "Peinture", "Favoris"]

INITIAL_VIDEOS_BY_CATEGORY = {
    "Dessin": [
        {"id": "rTgj1HxmUeg", "title": "Apprends à dessiner un lion !"},
        {"id": "v91oQN9y7dQ", "title": "Dessin facile : un chien mignon"},
        {"id": "Z5O8d9YVq9k", "title": "Tutoriel dessin pour enfants"}
    ],
    "Tutoriels": [
        {"id": "dQw4w9WgXcQ", "title": "Comment faire un nœud de lacet"},
        {"id": "XsT6rhvUuCA", "title": "Tutoriel pliage de papier"}
    ],
    "Bricolage": [
        {"id": "mQW6y4YcZ8c", "title": "Bricolage facile avec du carton"},
        {"id": "JkYXZxYxN2w", "title": "Crée ton robot en boîtes"}
    ],
    "Challenges": [
        {"id": "LXb3E3B8SdI", "title": "Le défi des 10 secondes !"},
        {"id": "pRpeEdMmmQ0", "title": "Challenge rigolo : saute sans rire"}
    ],
    "Peinture": [
        {"id": "kXZER8V1VvI", "title": "Peinture avec les doigts"},
        {"id": "FUSn1YP2qpk", "title": "Crée un arc-en-ciel en peinture"}
    ],
    "Favoris": []
}

# === 🛠️ Initialisation de la base de données ===
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

# === 🔁 Client OpenAI vers aimlapi ===
client = OpenAI(
    base_url="https://api.aimlapi.com/v1",
    api_key=AIML_API_KEY
)

def calculate_distance(pos1, pos2):
    return abs(pos1['h'] - pos2['h']) + abs(pos1['v'] - pos2['v'])

def minimax(position, target, depth, is_maximizing_player):
    if position == target:
        return 1, []
    if depth == 0:
        return -calculate_distance(position, target), []

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

# === 🤖 Async LLM Response via aimlapi ===
async def get_ai_response(prompt: str) -> str:
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a friendly science guide for children. Always answer in simple English. Just explain in the way that kids understand. Don't tell 'Here are four curiosity questions about Animal Adventures for children aged 6-10:'; just give the list of the answers."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Erreur de l'IA: {e}"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Démarrage de l'application : Initialisation de la base de données...")
    init_db()
    yield
    print("🛑 Arrêt de l'application.")

app = FastAPI(lifespan=lifespan)

# === 👤 Session utilisateur enrichie pour le rapport ===
class UserSession:
    def __init__(self, user_id, websocket):
        self.user_id = user_id
        self.websocket = websocket
        self.is_authenticated = True
        self.child_name = None
        self.avatar = None
        self.parent_email = None
        self.start_time = datetime.now()

        # 🔹 Données à suivre pour le rapport
        self.messages = []          # Tous les messages de l'enfant
        self.videos_viewed = []     # Vidéos vues
        self.categories_explored = set() # Catégories demandées

active_connections: list[UserSession] = []

def hash_password(password: str):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_viewed_video_ids(user_id: str):
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
        print(f"❌ Erreur lors de l'ajout de la vidéo vue : {e}")
    finally:
        conn.close()

async def generate_ai_response_structured(prompt: str):
    """Génère une réponse IA structurée en JSON."""
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": """
                Ton rôle est d'assister un enfant. Pour chaque requête, tu dois retourner une réponse au format JSON strict.
                Le JSON doit contenir deux clés :
                1. "ai_message": Un message court et bienveillant pour l'enfant.
                2. "search_query": Une requête concise pour rechercher des vidéos YouTube.

                Exemple de réponse :
                {
                  "ai_message": "Je vais te trouver de super vidéos de chats !",
                  "search_query": "vidéos de chats pour enfants"
                }
                """},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.7
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erreur IA : {e}")
        return {
            "ai_message": "Je n'ai pas pu générer de réponse pour l'instant. Peux-tu reformuler ?",
            "search_query": ""
        }

async def search_videos(query: str, user_id: str):
    """Recherche des vidéos YouTube (version simplifiée)."""
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
        print(f"❌ Erreur recherche YouTube : {e}")
        return []

# === 📧 GÉNÉRATION ET ENVOI DU RAPPORT PAR EMAIL ===
async def generate_activity_summary(session: UserSession):
    """Demande à l'IA de résumer l'activité de l'enfant."""
    try:
        prompt = f"""
        Tu es un éducateur bienveillant. Voici l'activité de {session.child_name} :
        - Messages envoyés : {', '.join([m['text'][:30] + '...' for m in session.messages[-5:]])}
        - Vidéos vues : {len(session.videos_viewed)}
        - Catégories explorées : {', '.join(session.categories_explored)}
        - Durée : {datetime.datetime.now() - session.start_time}

        Rédige un résumé chaleureux, positif et pédagogique (3-4 phrases) pour les parents.
        Mets en avant la curiosité, la créativité ou l'apprentissage.
        """
        response = await generate_ai_response_structured(prompt)
        return response.get('ai_message', "Votre enfant a exploré plusieurs sujets avec intérêt.")
    except:
        return "Votre enfant a exploré plusieurs sujets avec intérêt."

async def send_parent_report(session: UserSession):
    """Envoie un email au parent avec le rapport d'activité."""
    if not session.parent_email:
        print("❌ Aucun email parent défini.")
        return

    duration = datetime.datetime.now() - session.start_time
    summary = await generate_activity_summary(session)

    # 📄 Template HTML du rapport
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 700px; margin: auto; padding: 20px;">
        <h2>📊 Rapport d'activité - {session.child_name}</h2>
        <p>Bonjour !</p>
        <p>Votre enfant a utilisé <strong>WOO</strong> pendant <strong>{str(duration).split('.')[0]}</strong>.</p>

        <h3>📝 Messages envoyés</h3>
        <ul>
        {''.join(f'<li><em>{m["text"]}</em> ({m["timestamp"][:16]})</li>' for m in session.messages[-10:])}
        </ul>

        <h3>🎬 Vidéos vues ({len(session.videos_viewed)})</h3>
        <ul>
        {''.join(f'<li>{v["title"]}</li>' for v in session.videos_viewed[:5])}
        {f'<li>... et {len(session.videos_viewed) - 5} autres</li>' if len(session.videos_viewed) > 5 else ''}
        </ul>

        <h3>🔍 Catégories explorées</h3>
        <p>{', '.join(session.categories_explored) or 'Aucune'}</p>

        <h3>🧠 Résumé IA</h3>
        <p style="background-color: #f0f8ff; padding: 10px; border-radius: 5px; font-style: italic;">
            {summary}
        </p>

        <hr>
        <p><small>Ce rapport a été généré automatiquement par WOO. Ne pas répondre à cet email.</small></p>
    </body>
    </html>
    """

    # 📬 Préparation de l'email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"👶 Activité de {session.child_name} sur WOO"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = session.parent_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # 📤 Envoi
    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=EMAIL_ADDRESS,
            password=EMAIL_PASSWORD,
            start_tls=True
        )
        print(f"✅ Rapport envoyé à {session.parent_email}")
    except Exception as e:
        print(f"❌ Échec de l'envoi du rapport : {e}")

# === 🌐 WebSocket Principal ===
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_session = None

    # Envoyer les catégories
    await websocket.send_text(json.dumps({"type": "categories", "categories": INITIAL_CATEGORIES}))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            print("📩 Message reçu:", message)

            # === 🔐 Inscription ===
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
                        "message": "Cet email est déjà utilisé."
                    }))
                finally:
                    conn.close()

            # === 🔐 Connexion ===
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
                        "message": "Email ou mot de passe incorrect."
                    }))

            # === 📝 Requête de l'enfant ===
            elif message["type"] == "query":
                user_id = message.get("user_id")
                text = message.get("text", "").strip()
                if not user_id or not text: continue

                for s in active_connections:
                    if s.user_id == user_id:
                        s.messages.append({"text": text, "timestamp": datetime.now().isoformat()})
                        break
                
                # Appeler l'IA pour obtenir une réponse structurée
                ai_response = await generate_ai_response_structured(text)
                ai_message = ai_response.get("ai_message")
                search_query = ai_response.get("search_query")
                
                # Rechercher les vidéos
                videos = await search_videos(search_query, user_id)
                
                # Envoyer un seul message au client
                await websocket.send_text(json.dumps({
                    "type": "videos",
                    "message": ai_message,
                    "videos": videos
                }))

            # === 📚 Catégorie sélectionnée ===
            elif message["type"] == "category_query":
                cat = message.get("text", "").strip()
                user_id = message.get("user_id")
                if not cat: continue

                for s in active_connections:
                    if s.user_id == user_id:
                        s.categories_explored.add(cat)
                        break

                # Appeler l'IA pour obtenir une réponse structurée
                ai_response = await generate_ai_response_structured(f"Trouve-moi des vidéos sur le thème {cat} pour les enfants.")
                ai_message = ai_response.get("ai_message")
                search_query = ai_response.get("search_query")
                
                # Rechercher les vidéos
                videos = await search_videos(search_query, user_id)
                
                # Envoyer un seul message au client
                await websocket.send_text(json.dumps({
                    "type": "videos",
                    "message": ai_message,
                    "videos": videos
                }))
                
            # === 🎥 Vidéo vue ===
            elif message["type"] == "video_viewed":
                vid_id = message.get("video_id")
                vid_title = message.get("video_title")
                user_id = message.get("user_id")
                if vid_id and user_id:
                    add_viewed_video(user_id, vid_id)
                    for s in active_connections:
                        if s.user_id == user_id:
                            s.videos_viewed.append({
                                "id": vid_id,
                                "title": vid_title,
                                "timestamp": datetime.now().isoformat()
                            })
                            break
            elif message['type'] == "get_questions":
                theme = message.get("theme")
                print(f"Requête reçue pour le thème : {theme}")
                
                prompt = f"""
                Act as a science guide for children aged 6-10.
                Generate 4 simple and intriguing curiosity questions about {theme}.
                Answer in English.
                Do not include answers.
                Write each question on a new line.
                """
                ai_text = await get_ai_response(prompt)
                
                questions = [q.strip() for q in ai_text.split('\n') if q.strip()]
                
                await websocket.send_json({"type": "questions", "questions": questions})
                print("Questions envoyées au client.")

            elif message['type'] == "get_reponse":
                question = message.get("question")
                print(f"Requête reçue pour la question : {question}")
                
                prompt = f"""
                Act as a science guide for children aged 6-10.
                Explain in a simple and clear way the answer to the question '{question}'.
                Use analogies and easy-to-understand vocabulary.
                Keep the answer short, less than 3 sentences.
                Answer in English.
                """
                ai_text = await get_ai_response(prompt)
                
                await websocket.send_json({"type": "reponse", "reponse": ai_text})
                print("Réponse envoyée au client.")
            elif message.get("turn") == "ai":
                print("AI's turn. Calculating best move...")
                player_pos = message['playerPos']
                target_pos = message['targetPos']
                
                # Calculate the shortest path using a simple pathfinding approach
                path = []
                current_h = player_pos['h']
                current_v = player_pos['v']
                
                while current_h < target_pos['h']:
                    path.append('right')
                    current_h += 1
                while current_h > target_pos['h']:
                    path.append('left')
                    current_h -= 1
                while current_v < target_pos['v']:
                    path.append('down')
                    current_v += 1
                while current_v > target_pos['v']:
                    path.append('up')
                    current_v -= 1
                
                await websocket.send_text(json.dumps({ "aiPath": path }))
            
            elif message.get("blocks") is not None:
                blocks = message.get("blocks")
                print(f"Received blocks: {blocks}")
                system_prompt = (
                    "You are an AI assistant for a coding game. "
                    "The user provides a list of movement blocks: 'right', 'left', 'up', 'down'. "
                    "Your task is to: "
                    "1. Calculate the final horizontal (h) and vertical (v) position based on the blocks. "
                    "   'right' adds 1 to h, 'left' subtracts 1 from h. "
                    "   'up' subtracts 1 from v, 'down' adds 1 to v. "
                    "   Start position is (h=0, v=0)."
                    "2. Generate a formula showing the total horizontal and vertical moves (e.g., \"right + right - up = (2, 1)\")."
                    "3. Generate a simple, encouraging goal for the user based on the final position. "
                    "   Encourage them to reach a target point, like a corner or a specific spot on the grid. "
                    "   The goal must be a JSON object with 'goal', 'formula', and 'result'."
                )
                user_prompt = f"The list of blocks is: {blocks}. Please provide the formula, the final coordinates (as a result), and a new goal."
                try:
                    response = await asyncio.to_thread(
                        client.chat.completions.create,
                        model=LLM_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=100,
                        response_format={"type": "json_object"}
                    )
                    ai_response = response.choices[0].message.content.strip()
                    await websocket.send_text(ai_response)
                except Exception as e:
                    print(f"API error: {e}")
                    await websocket.send_text(json.dumps({"error": "Failed to get a goal from the AI."}))
            
            else:
                await websocket.send_text(json.dumps({"error": "Invalid data received."}))
    except WebSocketDisconnect:
        if user_session and user_session in active_connections:
            await send_parent_report(user_session)  # 🔥 Envoi du rapport ici
            active_connections.remove(user_session)
        print("🔌 Client déconnecté.")
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        if user_session in active_connections:
            active_connections.remove(user_session)