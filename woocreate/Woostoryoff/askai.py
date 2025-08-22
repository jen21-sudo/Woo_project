import os
from groq import Groq

# Placez votre clé API Groq dans une variable d'environnement pour des raisons de sécurité
# Ou remplacez-la directement ici si c'est pour un usage personnel
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def ask_ai(prompt_user: str, prompt_systeme: str) -> str:
    """
    Interagit avec l'API Groq pour générer du texte.
    """
    if not GROQ_API_KEY:
        return "Erreur : La clé API de Groq n'est pas configurée."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_user}
            ],
            model="llama3-8b-8192" # ou un autre modèle
        )
        return chat_completion.choices[0].message.content

    except Exception as e:
        return f"Une erreur est survenue lors de l'appel à l'API : {e}"