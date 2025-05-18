from pymongo import MongoClient

MONGODB_URI: str = "mongodb+srv://thilinahansana1100:1100@timetable.lsozv.mongodb.net/?retryWrites=true&w=majority&appName=timetable"


client = MongoClient(MONGODB_URI)
db = client["time_table_whiz"]

