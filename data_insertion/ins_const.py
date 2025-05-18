from pymongo import MongoClient
from datetime import datetime
from database import client, db
import json

constraints_collection = db["constraints"]

constraints = []
with open('data_insertion/constraints.json', 'r') as file:
    constraints = json.load(file)

default_settings = {}
default_applicability = {
    "teachers": None,
    "students": None,
    "activities": None,
    "spaces": None,
    "all_teachers": False,
    "all_students": False,
    "all_activities": False
}
for constraint in constraints:
    constraint.update({
        "settings": default_settings,
        "applicability": default_applicability,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })

result = constraints_collection.insert_many(constraints)

print(f"Inserted {len(result.inserted_ids)} constraints into the database.")
