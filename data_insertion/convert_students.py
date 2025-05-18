import json
import random
import os

def load_module_codes(modules_file):
    with open(modules_file, 'r') as f:
        modules = json.load(f)
    
    module_codes = {}
    for module in modules:
        semester = module["semester"]
        if semester not in module_codes:
            module_codes[semester] = []
        module_codes[semester].append({
            "code": module["code"],
            "specialization": module["specialization"]
        })
    
    return module_codes

def generate_student_id(index):
    return f"IT{index:07d}"

def generate_username(first_name, last_name):
    return f"{first_name.lower()}{last_name.lower()[0]}123"

def generate_email(first_name, last_name):
    return f"{first_name.lower()}.{last_name.lower()}@example.com"

def get_year_from_semester(semester):
    return int(semester[1])

def generate_attend_days():
    return random.choice(["weekday"])

def generate_specialization():
    specializations = ["IT", "SE", "CS", "ISE", "IM"]
    return random.choice(specializations)

def generate_year_group(year, semester, specialization):
    return f"Y{year}S{semester}.{specialization}.{random.randint(1, 5)}"

def transform_students(input_file, output_file, modules_file):
    module_codes = load_module_codes(modules_file)
    semesters = list(module_codes.keys())
    
    semester_limits = {
        "Y1S1": 400, "Y1S2": 400,
        "Y2S1": 400, "Y2S2": 400,
        "Y3S1": 300, "Y3S2": 300,
        "Y4S1": 300, "Y4S2": 300
    }
    semester_counts = {key: 0 for key in semester_limits}
    
    with open(input_file, 'r') as f:
        students = json.load(f)

    transformed_students = []
    index = 1
    
    for student in students:
        semester = None
        for sem in semester_limits:
            if semester_counts[sem] < semester_limits[sem]:
                semester = sem
                semester_counts[sem] += 1
                break
        
        if semester is None:
            break  # Stop when all slots are filled
        
        year = get_year_from_semester(semester)
        specialization = generate_specialization()
        available_modules = [module["code"] for module in module_codes.get(semester, []) if specialization in module["specialization"]]
        
        # Ensure at least 3 subjects, maximum 4
        subject_count = min(4, max(3, len(available_modules)))
        subjects = random.sample(available_modules, min(subject_count, len(available_modules))) if available_modules else []
        
        # If we couldn't get 3 subjects for the specialization, fill with any available ones from the semester
        if len(subjects) < 3 and module_codes.get(semester):
            all_modules = [module["code"] for module in module_codes.get(semester, [])]
            remaining_modules = [m for m in all_modules if m not in subjects]
            additional_needed = 3 - len(subjects)
            if remaining_modules and additional_needed > 0:
                subjects.extend(random.sample(remaining_modules, min(additional_needed, len(remaining_modules))))
        
        attend_days = generate_attend_days()
        year_group = generate_year_group(year, semester[3], specialization)

        transformed_student = {
            "id": generate_student_id(index),
            "first_name": student["first_name"],
            "last_name": student["last_name"],
            "username": generate_username(student["first_name"], student["last_name"]),
            "email": generate_email(student["first_name"], student["last_name"]),
            "telephone": "+94771234567",
            "position": "Undergraduate",
            "role": "student",
            "hashed_password": "test123",
            "subjects": subjects,
            "year": year,
            "subgroup": semester,
            "year_group": year_group,
            "specialization": specialization,
            "attend_days": attend_days
        }
        
        transformed_students.append(transformed_student)
        index += 1
    
    with open(output_file, 'w') as f:
        json.dump(transformed_students, f, indent=4)

# Use absolute paths or resolve paths relative to the script
# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Create absolute paths by joining with the script directory
input_file = os.path.join(script_dir, "students.json")
output_file = os.path.join(script_dir, "transformed_students.json")
modules_file = os.path.join(script_dir, "modules.json")

transform_students(input_file, output_file, modules_file)
