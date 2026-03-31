from models.database import fetch_all
import json

try:
    cats = fetch_all("SELECT id, name, image FROM categories")
    print(json.dumps(cats))
except Exception as e:
    print(f"Error: {e}")
