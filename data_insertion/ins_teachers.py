from pymongo import MongoClient
from datetime import datetime
from database import client, db
import json
from passlib.context import CryptContext
import os

collection = db["Users"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "TimeTableWhiz"
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def load_data_from_json(json_file):
    with open(json_file, 'r') as file:
        data = json.load(file)
    return data

def add_hashed_passwords_and_insert(data, batch_size=100):
    try:
        total_inserted = 0
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            # Hash passwords for this batch
            for item in batch:
                if "hashed_password" in item:
                    item["hashed_password"] = hash_password(item["hashed_password"])
            
            # Insert the batch
            result = collection.insert_many(batch)
            total_inserted += len(result.inserted_ids)
            print(f"Batch {i//batch_size + 1}: Inserted {len(result.inserted_ids)} documents")
        
        print(f"Total {total_inserted} documents inserted successfully.")
    except Exception as e:
        print(f"Error at batch starting with index {i}: {e}")

# Use absolute paths to resolve file location issues
# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Create absolute paths by joining with the script directory
data_file = os.path.join(script_dir, "transformed_students.json")
print(f"Looking for file at: {data_file}")  # Debug statement to verify path

try:
    data = load_data_from_json(data_file)
    # Process and insert in batches of 100
    add_hashed_passwords_and_insert(data, batch_size=100)
except FileNotFoundError:
    print(f"Error: File not found at {data_file}")
    print("Please make sure the file exists at the correct location.")