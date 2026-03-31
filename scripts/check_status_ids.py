import sys
import os
sys.path.append(os.getcwd())

from models.database import fetch_all

def find_status_id():
    try:
        statuses = fetch_all("SELECT * FROM delivery_status")
        print("Available Statuses:")
        for s in statuses:
            print(f"ID: {s['id']}, Name: {s['status_name']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_status_id()
