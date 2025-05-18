import json
import random
import os
from collections import defaultdict

# Define base directory and paths
BASE_DIR = '/Users/thilinahansana/Desktop/Research/sudu/Latest Version/University-Scheduler-Backend-latest'
TEACHERS_PATH = os.path.join(BASE_DIR, 'data_insertion/teachers.json')
MODULES_PATH = os.path.join(BASE_DIR, 'data_insertion/modules.json')
OUTPUT_PATH = os.path.join(BASE_DIR, 'data_insertion/updated_teachers.json')

def load_data():
    """Load teachers and modules data from JSON files"""
    with open(TEACHERS_PATH, 'r') as f:
        teachers = json.load(f)
    
    with open(MODULES_PATH, 'r') as f:
        modules = json.load(f)
    
    return teachers, modules

def get_module_assignments(teachers):
    """Get the current module to teachers assignments"""
    module_assignments = defaultdict(list)
    for teacher in teachers:
        for subject in teacher.get("subjects", []):
            module_assignments[subject].append(teacher["id"])
    return module_assignments

def assign_modules(teachers, modules):
    """Assign modules to teachers - each module must have at least 3 teachers and each teacher gets exactly 3 modules"""
    # Reset all teacher assignments
    for teacher in teachers:
        teacher["subjects"] = []
    
    # Get all module codes
    all_module_codes = [module["code"] for module in modules]
    
    # Calculate if we have enough teachers for all modules
    total_teachers = len(teachers)
    total_modules = len(all_module_codes)
    
    # Each module needs 3 teachers, and each teacher handles 3 modules
    required_teacher_module_slots = total_modules * 3
    available_teacher_module_slots = total_teachers * 3
    
    print(f"Total modules: {total_modules}")
    print(f"Total teachers: {total_teachers}")
    print(f"Required teacher-module slots: {required_teacher_module_slots}")
    print(f"Available teacher-module slots: {available_teacher_module_slots}")
    
    if required_teacher_module_slots > available_teacher_module_slots:
        print("Warning: Not enough teachers to assign 3 per module. Some modules may have fewer teachers.")
    
    # First, assign 3 modules to each teacher
    module_assignments = defaultdict(list)
    
    # Shuffle modules to give equal priority
    random.shuffle(all_module_codes)
    
    # Phase 1: Ensure each module has at least 3 teachers
    for module_code in all_module_codes:
        needed_teachers = 3 - len(module_assignments[module_code])
        
        if needed_teachers <= 0:
            continue
            
        # Find teachers who can take more modules and don't teach this module yet
        available_teachers = [
            t for t in teachers 
            if len(t["subjects"]) < 3 and 
            module_code not in t["subjects"] and
            t["id"] not in module_assignments[module_code]
        ]
        
        # Sort by current workload (fewer modules first)
        available_teachers.sort(key=lambda t: len(t["subjects"]))
        
        # Assign the module to teachers
        for i in range(min(needed_teachers, len(available_teachers))):
            teacher = available_teachers[i]
            teacher["subjects"].append(module_code)
            module_assignments[module_code].append(teacher["id"])
            print(f"Assigned {module_code} to {teacher['id']} (module completion)")
    
    # Phase 2: Ensure each teacher has exactly 3 modules
    for teacher in teachers:
        slots_available = 3 - len(teacher["subjects"])
        
        if slots_available <= 0:
            continue
            
        # Find modules that this teacher isn't teaching yet
        # Prioritize modules with fewer than 3 teachers
        available_modules = [
            code for code in all_module_codes 
            if code not in teacher["subjects"]
        ]
        
        # Sort by number of teachers (fewer first)
        available_modules.sort(key=lambda code: len(module_assignments[code]))
        
        # Assign modules
        for i in range(min(slots_available, len(available_modules))):
            module_code = available_modules[i]
            teacher["subjects"].append(module_code)
            module_assignments[module_code].append(teacher["id"])
            print(f"Assigned {module_code} to {teacher['id']} (teacher completion)")
    
    return teachers, module_assignments

def save_updated_teachers(teachers, output_path=OUTPUT_PATH):
    """Save the updated teacher data to a JSON file"""
    with open(output_path, 'w') as f:
        json.dump(teachers, f, indent=2)
    print(f"Updated teachers data saved to {output_path}")

def generate_summary(teachers, module_assignments):
    """Generate statistics and summary of module assignments"""
    print("\n----- SUMMARY -----")
    print(f"Total teachers: {len(teachers)}")
    print(f"Total modules: {len(module_assignments)}")
    
    # Count modules per teacher
    modules_per_teacher = [len(t.get("subjects", [])) for t in teachers]
    print(f"Average modules per teacher: {sum(modules_per_teacher)/len(teachers):.2f}")
    print(f"Min modules per teacher: {min(modules_per_teacher)}")
    print(f"Max modules per teacher: {max(modules_per_teacher)}")
    
    # Count teachers per module
    teachers_per_module = [len(teachers_list) for teachers_list in module_assignments.values()]
    print(f"Average teachers per module: {sum(teachers_per_module)/len(module_assignments):.2f}")
    print(f"Min teachers per module: {min(teachers_per_module)}")
    print(f"Max teachers per module: {max(teachers_per_module)}")
    
    # Validate requirements
    modules_with_few_teachers = {code: teachers_list for code, teachers_list 
                              in module_assignments.items() if len(teachers_list) < 3}
    if modules_with_few_teachers:
        print("\nWarning: The following modules have fewer than 3 teachers:")
        for code, teachers_list in modules_with_few_teachers.items():
            print(f"{code}: {len(teachers_list)} teachers")
    else:
        print("\n✓ All modules have at least 3 teachers")
    
    teachers_with_wrong_modules = [t for t in teachers if len(t.get("subjects", [])) != 3]
    if teachers_with_wrong_modules:
        print("\nWarning: The following teachers don't have exactly 3 modules:")
        for teacher in teachers_with_wrong_modules:
            print(f"{teacher['id']} - {teacher['first_name']} {teacher['last_name']}: {len(teacher.get('subjects', []))} modules")
    else:
        print("✓ All teachers have exactly 3 modules")

def main():
    print("Loading data...")
    teachers, modules = load_data()
    
    print("Assigning modules to teachers...")
    updated_teachers, module_assignments = assign_modules(teachers, modules)
    
    generate_summary(updated_teachers, module_assignments)
    
    print("\nSaving updated data...")
    save_updated_teachers(updated_teachers)
    
    print("\nProcess completed successfully!")

if __name__ == "__main__":
    main()