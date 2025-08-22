# Fichier : main.py

from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from groq import Groq
import os
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialise le client Groq une seule fois au début de l'application
client = Groq(api_key="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") 

# Fonction asynchrone pour interagir avec l'API de l'IA (Groq)
async def get_ai_response(prompt: str) -> str:
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="llama3-8b-8192",
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

# Route pour servir la page d'accueil
@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Route WebSocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Connexion WebSocket acceptée.")

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "get_questions":
                theme = data.get("theme")
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

            elif message_type == "get_reponse":
                question = data.get("question")
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
    except Exception as e:
        print(f"Erreur WebSocket: {e}")