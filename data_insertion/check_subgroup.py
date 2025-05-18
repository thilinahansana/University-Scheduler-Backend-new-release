import json

def check_subgroup_counts(file_path):
    with open(file_path, 'r') as file:
        activities = json.load(file)
    
    for activity in activities:
        code = activity.get('code')
        subgroup_ids = activity.get('subgroup_ids', [])
        count = len(subgroup_ids)
        print(f"Activity Code: {code}, Subgroup Count: {count}")

if __name__ == "__main__":
    file_path = 'data_insertion/activities.json'
    check_subgroup_counts(file_path)
