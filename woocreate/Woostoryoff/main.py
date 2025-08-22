import asyncio
import websockets
import json
from groq import Groq

# Remplacez par votre clé API de Groq
# Vous pouvez la trouver sur https://console.groq.com/keys  
GROQ_API_KEY = "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"

# Fonction pour appeler l'API Groq
async def ask_ai(data):
    """
    Appelle l'API de Groq pour générer une réponse basée sur les données d'entrée,
    en utilisant des prompts par défaut si les champs sont vides.
    """
    client = Groq(api_key=GROQ_API_KEY)
    
    # Définir des prompts par défaut en anglais, simples et enfantins
    default_prompts = {
        "personnage": "a kind animal or a brave little kid",
        "scene": "a magical forest or a colorful planet",
        "scenario": "a fun adventure with a happy ending"
    }

    # Utiliser la valeur de l'utilisateur ou le prompt par défaut
    personnage = data.get("personnage") or default_prompts["personnage"]
    scene = data.get("scene") or default_prompts["scene"]
    scenario = data.get("scenario") or default_prompts["scenario"]

    # Message utilisateur clair et simple
    user_message = (
        f"My character is: {personnage}. "
        f"The story happens in: {scene}. "
        f"Here is what happens: {scenario}. "
        "Can you make a fun and simple story for a young child? "
        "Use easy words. No stars, no markdown, no bold. Just a sweet story."
    )

    try:
        chat_completion = await asyncio.to_thread(
            client.chat.completions.create,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a friendly storyteller for young children. "
                        "Create a short, magical, and easy-to-understand story in English. "
                        "Use simple words. Do not use any formatting like **, #, or *."
                        "Do not say 'Once upon a time' every time. Make it warm and fun. "
                        "Keep it under 150 words."
                    ),
                },
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            model="llama3-8b-8192",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Sorry, something went wrong while creating the story: {str(e)}"

# Le reste du code reste inchangé
async def handler(websocket):
    print(f"Nouvelle connexion WebSocket sur le chemin: {websocket}")
    try:
        async for message in websocket:
            print(f"Message reçu: {message}")
            
            try:
                data = json.loads(message)
                
                ai_response = await ask_ai(data)
                
                await websocket.send(ai_response)

            except json.JSONDecodeError:
                print("Message non-JSON reçu.")
                await websocket.send("Error: The message received is not valid JSON.")

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connexion fermée avec le code {e.code}, raison: {e.reason}")
    finally:
        print("Connexion WebSocket fermée.")

async def main():
    async with websockets.serve(handler, "localhost", 3000):
        print("Serveur WebSocket démarré sur ws://localhost:3000")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())