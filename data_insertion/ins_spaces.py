from pymongo import MongoClient
from datetime import datetime
from database import db
import json

collection = db["Spaces"]

def load_spaces_from_json(file_path):
    with open(file_path, 'r') as file:
        spaces = json.load(file)
    return spaces

def insert_spaces(spaces):
    try:
        result = collection.insert_many(spaces)
        print(f"Inserted {len(result.inserted_ids)} spaces successfully.")
    except Exception as e:
        print(f"Error inserting spaces: {e}")

spaces = load_spaces_from_json('data_insertion/spaces.json')
insert_spaces(spaces)
