import json
import os
import uuid
from typing import Dict, Any

# Nom du fichier pour la persistance des données
DATA_FILE = "data.json"

def load_data() -> Dict[str, Any]:
    """
    Charge les données depuis le fichier JSON.
    Retourne un dictionnaire avec un ID unique pour chaque soumission.
    """
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                # Gère le cas où le fichier est vide ou corrompu
                return {}
    return {}

def save_data(user_input: Dict[str, str]) -> str:
    """
    Ajoute les nouvelles données de l'utilisateur dans le fichier JSON existant.
    Génère un ID unique pour la soumission.
    Retourne l'ID généré.
    """
    existing_data = load_data()
    # Génère un ID unique pour cette soumission
    submission_id = str(uuid.uuid4())
    
    # Stocke les données sous cet ID
    existing_data[submission_id] = user_input
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
        
    print(f"Données enregistrées dans {DATA_FILE} sous l'ID : {submission_id}")
    return submission_id