from pymongo import MongoClient
from database import client, db
import json

collection = db["Users"]

def load_data_from_json(json_file):
    with open(json_file, 'r') as file:
        data = json.load(file)
    return data

def delete_teachers(data, batch_size=10):
    try:
        total_deleted = 0
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            ids_to_delete = [item['id'] for item in batch]
            
            # Delete the batch
            result = collection.delete_many({"id": {"$in": ids_to_delete}})
            total_deleted += result.deleted_count
            print(f"Batch {i//batch_size + 1}: Deleted {result.deleted_count} documents")
        
        print(f"Total {total_deleted} documents deleted successfully.")
    except Exception as e:
        print(f"Error at batch starting with index {i}: {e}")

def delete_students(batch_size=100):
    try:
        # Get all student records from the database
        students = list(collection.find({"role": "student"}))
        total_students = len(students)
        
        if total_students == 0:
            print("No students found in the database.")
            return
            
        print(f"Found {total_students} students in the database.")
        
        total_deleted = 0
        for i in range(0, total_students, batch_size):
            batch = students[i:i + batch_size]
            ids_to_delete = [item['id'] for item in batch]
            
            # Delete the batch
            result = collection.delete_many({"id": {"$in": ids_to_delete}, "role": "student"})
            total_deleted += result.deleted_count
            print(f"Batch {i//batch_size + 1}: Deleted {result.deleted_count} student documents")
        
        print(f"Total {total_deleted} student documents deleted successfully.")
    except Exception as e:
        print(f"Error during student deletion: {e}")

# Call the function to delete students instead of teachers
delete_students(batch_size=100)
