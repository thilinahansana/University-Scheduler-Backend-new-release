from pymongo import MongoClient

MONGODB_URI: str = "mongodb+srv://ivCodes:doNF7RbKedWTtB5S@timetablewiz-cluster.6pnyt.mongodb.net/?retryWrites=true&w=majority&appName=TimeTableWiz-Cluster"


client = MongoClient(MONGODB_URI)
db = client["time_table_whiz"]

