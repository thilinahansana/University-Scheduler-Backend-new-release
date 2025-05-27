from utils.database import db

def get_faculties():
    faculties = list(db["faculties"].find())
    return faculties

def get_days():
    days = list(db["days_of_operation"].find())
    return days

def get_years():
    years = list(db["Years"].find())
    return years

def get_periods():
    periods = list(db["periods_of_operation"].find())
    
    # Sort periods by name (P1, P2, etc.)
    # Extract the numeric part from period names for proper sorting
    def get_period_number(period):
        # Extract numeric part from period name (e.g., 'P1' -> 1)
        name = period.get('name', '')
        if name.startswith('P') and name[1:].isdigit():
            return int(name[1:])
        return float('inf')  # Put any non-standard named periods at the end
    
    # Sort periods based on the extracted number
    sorted_periods = sorted(periods, key=get_period_number)
    
    return sorted_periods

def get_spaces():
    spaces = list(db["Spaces"].find())
    return spaces

def get_activities():
    activities = list(db["Activities"].find())
    return activities

def get_modules():
    modules = list(db["modules"].find())
    return modules

def get_teachers():
    teachers = list(db["Users"].find({
        "role": "faculty"
    }))
    return teachers

def get_students():
    students = list(db["Users"].find({
        "role": "student"
    }))
    return students

def get_timetables():
    timetable = list(db["Timetable"].find())
    return timetable

def get_constraints():
    constraints = list(db["constraints"].find())
    return constraints