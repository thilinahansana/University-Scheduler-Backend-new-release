import json

def validate_modules(file_path):
    with open(file_path, 'r') as file:
        modules = json.load(file)
    
    codes = set()
    semesters = set()
    all_semesters = {"Y1S1", "Y1S2", "Y2S1", "Y2S2", "Y3S1", "Y3S2", "Y4S1", "Y4S2"}
    
    for module in modules:
        code = module["code"]
        semester = module["semester"]
        
        if code in codes:
            print(f"Duplicate code found: {code}")
        else:
            codes.add(code)
        
        semesters.add(semester)
    
    missing_semesters = all_semesters - semesters
    if missing_semesters:
        print(f"Missing semesters: {', '.join(missing_semesters)}")
    else:
        print("All semesters are covered.")
    
    if len(codes) == len(modules):
        print("All codes are unique.")
    else:
        print("There are duplicate codes.")

if __name__ == "__main__":
    validate_modules('/Users/thilinahansana/Desktop/Research/sudu/Latest Version/University-Scheduler-Backend-latest/data_insertion/modules.json')
