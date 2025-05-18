from pymongo import MongoClient
from datetime import datetime
from database import db
import json


# days_collection = db['days_of_operation']
module_collection = db['modules']
years_collection = db['Years']
periods_collection = db['periods_of_operation']

# Path to the JSON file
json_file_path = 'data_insertion/modules.json'

# Read the JSON file
with open(json_file_path, 'r') as file:
    days_of_operation = json.load(file)

# Prepare the data for insertion
for day in days_of_operation:
    day.update({
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

# Insert data into the days_of_operation collection
result = module_collection.insert_many(days_of_operation)

print(f"Inserted {len(result.inserted_ids)} days of operation into the database.")

