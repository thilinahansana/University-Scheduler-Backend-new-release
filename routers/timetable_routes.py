from fastapi import APIRouter, HTTPException, Depends, Query
from routers.user_router import get_current_user
from utils.database import db
from typing import List, Dict
from generator.algorithms.ga.ga import *
from generator.algorithms.co.co_v2 import *
# from generator.algorithms.rl.rl_train import *
from generator.algorithms.rl.rl import *
from generator.algorithms.eval.eval import *
from generator.algorithms.bc.bc_v1 import *
from generator.algorithms.pso.pso_v1 import *
from datetime import datetime
from bson import ObjectId
from models.timetable_model import Timetable
from utils.timetable_validator import ConflictChecker


router = APIRouter()

@router.post("/generate")
async def generate_timetable(current_user: dict = Depends(get_current_user)):
    # Example usage of your scheduling algorithm:
    sol = generate_co()  # The solution returned by your ACO-based function
    save_timetable(sol, "CO", current_user)
    bc = generate_bco()
    save_timetable(bc, "BC", current_user)
    pso = generate_pso()
    save_timetable(pso, "PSO", current_user)
    # Save solution under "CO" algorithm name
    
    return {"message": "Timetable generated using CO."}

def map_subgroup_to_semester(subgroup_id: str):
    """
    Map activity subgroup format (like 'Y1S1.IT.1') to a semester format (like 'SEM101').
    Adjust as necessary for your naming convention.
    """
    mapping = {
        "Y1S1": "SEM101",
        "Y1S2": "SEM102",
        "Y2S1": "SEM201",
        "Y2S2": "SEM202",
        "Y3S1": "SEM301",
        "Y3S2": "SEM302",
        "Y4S1": "SEM401",
        "Y4S2": "SEM402"
    }
    
    # If the entire subgroup_id is exactly in the mapping, return it
    if subgroup_id in mapping:
        return mapping[subgroup_id]
    
    # Otherwise, try splitting on the first dot
    if '.' in subgroup_id:
        prefix = subgroup_id.split('.', 1)[0]
        if prefix in mapping:
            return mapping[prefix]
    
    return None  # No known mapping

def save_timetable(li, algorithm, current_user):
    """
    Saves the timetable solution to the DB, mapped by semester.
    
    Fix #1: only append each activity once per solution.
    Fix #2: remove the stray period in generate_timetable_code.
    """
    # If no solution was returned
    if li is None:
        print(f"Warning: No timetable data received for algorithm {algorithm}. Nothing to save.")
        db["notifications"].insert_one({
            "message": f"Failed to generate timetable using {algorithm}. No data was produced.",
            "type": "error",
            "read": False,
            "recipient": current_user["id"]
        })
        return

    # List all valid semester codes you expect
    subgroups = [
        "SEM101", "SEM102", "SEM201", "SEM202",
        "SEM301", "SEM302", "SEM401", "SEM402"
    ]
    
    # Create dict to hold final activities for each semester
    semester_timetables = {semester: [] for semester in subgroups}

    for activity in li:
        # Some activities have multiple subgroups
        if isinstance(activity["subgroup"], list):
            subgroup_ids = activity["subgroup"]
        else:
            subgroup_ids = [activity["subgroup"]]

        # We'll break after the first successful mapping if the activity 
        # can only truly belong to one semester.
        mapped = False
        for subgroup_id in subgroup_ids:
            mapped_id = map_subgroup_to_semester(subgroup_id)
            if mapped_id and mapped_id in semester_timetables:
                # Add the activity to this semester
                semester_timetables[mapped_id].append(activity)
                mapped = True
                # Avoid duplicating the same activity multiple times 
                # if multiple subgroups map to the same semester
                break  
        
        if not mapped:
            print(f"Warning: Could not map any subgroup in: {subgroup_ids}")
            print(f"Skipping activity: {activity}")

    # Sort your semester keys in a fixed order
    sorted_semesters = sorted(semester_timetables.keys(), key=lambda x: subgroups.index(x))

    # Write to DB
    for index, semester in enumerate(sorted_semesters):
        activities = semester_timetables[semester]
        
        db["Timetable"].replace_one(
            {
                "$and": [
                    {"semester": semester},
                    {"algorithm": algorithm}
                ]
            },
            {
                "code": generate_timetable_code(index, algorithm),
                "algorithm": algorithm,
                "semester": semester,
                "timetable": activities
            },
            upsert=True
        )

        db["old_timetables"].insert_one({
            "code": generate_timetable_code(index, algorithm),
            "algorithm": algorithm,
            "semester": semester,
            "timetable": activities,
            "date_created": datetime.now()
        })

    # Send a notification to the user
    db["notifications"].insert_one({
        "message": f"New timetable generated using {algorithm}",
        "type": "success",
        "read": False,
        "recipient": current_user["id"]
    })

def generate_timetable_code(index, algorithm):
    """
    Example code generator for stored timetables.
    Fix #2: removed the trailing period.
    """
    return f"{algorithm}-TT000{index}"

@router.get("/timetables")
async def get_timetables():
    timetables = list(db["Timetable"].find())
    cleaned_timetables = clean_mongo_documents(timetables)
    eval =  db["settings"].find_one({"option": "latest_score"})
    eval = clean_mongo_documents(eval)
    
    for algorithm, scores in eval["value"].items():
        average_score = sum(scores) / len(scores)
        eval[algorithm] = {
            "average_score": average_score,
        }
    
    out ={
        "timetables": cleaned_timetables,
        "eval": eval
    }
    
    return out

@router.post("/select")
async def select_algorithm(algo: dict, current_user: dict = Depends(get_current_user)):
    result = db["settings"].find_one({"option": "selected_algorithm"})
    if result:
        db["settings"].update_one(
            {"option": "selected_algorithm"},
            {"$set": {"value": algo["algorithm"]}}
        )
    else:
        db["settings"].insert_one({"option": "selected_algorithm", "value": algo})
    return {"message": "Algorithm selected", "selected_algorithm": algo}

@router.get("/selected")
async def get_selected_algorithm(current_user: dict = Depends(get_current_user)):
    result = db["settings"].find_one({"option": "selected_algorithm"})
    if result:
        return {"selected_algorithm": result["value"]}
    return {"selected_algorithm": None}

@router.get("/notifications")
async def get_notifications(current_user: dict = Depends(get_current_user)):
    notifications = list(db["notifications"].find({
        "recipient": current_user["id"],
        "read": False
    }))
    notifications = clean_mongo_documents(notifications)
    return notifications

@router.put("/notifications/{notification_id}")
async def mark_notification_as_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    result = db["notifications"].update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@router.patch("/timetable/{timetable_id}/activity/{session_id}")
async def super_update_session(
    timetable_id: str,
    session_id: str,
    partial_data: Dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Partially update (PATCH) a single scheduled session in a timetable. 
    The request body can contain only the fields to be changed, or multiple fields. 
    We do a conflict check before saving changes. 
    If conflicts are found, we discard the changes and return an error.
    """
    checker = ConflictChecker(db)

    # 1) Retrieve the timetable
    timetable = db["Timetable"].find_one({"_id": ObjectId(timetable_id)})
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")

    existing_activities = timetable.get("timetable", [])

    # 2) Locate the session to patch
    target_session = None
    for activity in existing_activities:
        if activity.get("session_id") == session_id:
            target_session = activity
            break
    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 3) Make an in-memory copy of the target session for conflict checks
    updated_session = dict(target_session)  # shallow copy
    
    # 4) Process special fields that need formatting
    for k, v in partial_data.items():
        # If you're not allowing session_id changes, skip that key
        if k == "session_id":
            continue
            
        # Special handling for period field to ensure proper structure
        if k == "period" and isinstance(v, list):
            # Format the periods with complete structure
            period_objects = []
            for period_item in v:
                # If it's just a name string, convert it to proper object
                if isinstance(period_item, str):
                    period_name = period_item
                    period_details = db["Periods"].find_one({"name": period_name})
                    if period_details:
                        period_objects.append({
                            "_id": period_details.get("_id"),
                            "name": period_details.get("name"),
                            "long_name": period_details.get("long_name"),
                            "is_interval": period_details.get("is_interval", False),
                            "created_at": period_details.get("created_at"),
                            "updated_at": period_details.get("updated_at"),
                            "index": period_details.get("index", 0)
                        })
                    else:
                        period_objects.append({"name": period_name})
                # If it's already an object but may be incomplete
                elif isinstance(period_item, dict) and "name" in period_item:
                    period_name = period_item["name"]
                    # If it only has name, get full details
                    if len(period_item.keys()) == 1:
                        period_details = db["Periods"].find_one({"name": period_name})
                        if period_details:
                            period_objects.append({
                                "_id": period_details.get("_id"),
                                "name": period_details.get("name"),
                                "long_name": period_details.get("long_name"),
                                "is_interval": period_details.get("is_interval", False),
                                "created_at": period_details.get("created_at"),
                                "updated_at": period_details.get("updated_at"),
                                "index": period_details.get("index", 0)
                            })
                        else:
                            period_objects.append({"name": period_name})
                    else:
                        # If it has some fields but maybe not all
                        period_details = db["Periods"].find_one({"name": period_name})
                        if period_details:
                            complete_period = {
                                "_id": period_details.get("_id"),
                                "name": period_details.get("name"),
                                "long_name": period_details.get("long_name"),
                                "is_interval": period_details.get("is_interval", False),
                                "created_at": period_details.get("created_at"),
                                "updated_at": period_details.get("updated_at"),
                                "index": period_details.get("index", 0)
                            }
                            period_objects.append(complete_period)
                        else:
                            period_objects.append(period_item)  # Keep as is if no details found
            
            # Sort periods by index
            period_objects.sort(key=lambda p: p.get("index", 0) if isinstance(p, dict) else 0)
            
            # Update the period field with properly formatted objects
            updated_session[k] = period_objects
            
            # Update duration if needed to match period count
            if len(period_objects) != updated_session.get("duration", 0):
                updated_session["duration"] = len(period_objects)
        # Special handling for day field
        elif k == "day" and isinstance(v, str):
            # Convert day string to proper object format
            day_details = db["Days"].find_one({"name": v})
            if day_details:
                updated_session[k] = {
                    "_id": day_details.get("_id"),
                    "name": day_details.get("name"),
                    "long_name": day_details.get("long_name")
                }
            else:
                updated_session[k] = v
        else:
            # All other fields, just copy as is
            updated_session[k] = v

    # 5) Run conflict checks on the updated session
    #    a) internal conflicts
    conflicts_internal = checker.check_single_timetable_conflicts(timetable_id, [updated_session], session_id)
    #    b) cross-timetable conflicts (comparing updated session to other timetables)
    algorithm = timetable.get("algorithm", "")
    conflicts_cross = checker.check_cross_timetable_conflicts([updated_session], timetable_id, algorithm)

    all_conflicts = conflicts_internal + conflicts_cross
    if all_conflicts:
        # 6) If we have conflicts, return an error (and do NOT persist changes).
        return {
            "message": "Conflicts detected. Changes were not saved.",
            "conflicts": all_conflicts
        }

    # 7) If no conflicts, commit the updated session to DB
    updated_activities = []
    for act in existing_activities:
        if act.get("session_id") == session_id:
            updated_activities.append(updated_session)
        else:
            updated_activities.append(act)

    db["Timetable"].update_one(
        {"_id": ObjectId(timetable_id)},
        {"$set": {"timetable": updated_activities}}
    )

    # 8) Log the change for audit purposes
    db["timetable_change_log"].insert_one({
        "session_id": session_id,
        "timetable_id": timetable_id,
        "change_type": "direct_update",
        "before": target_session,
        "after": updated_session,
        "changed_by": current_user["id"],
        "changed_at": datetime.now()
    })

    return {
        "message": "Session updated successfully. No conflicts found.",
        "updated_session_id": session_id
    }

@router.get("/timetable/{timetable_id}/conflicts")
async def check_timetable_conflicts(
    timetable_id: str,
    activities: List[Dict],
    current_user: dict = Depends(get_current_user)
):
    """
    Check for conflicts without actually updating the timetable
    """
    checker = ConflictChecker(db)
    
    # Validate activity structure
    validation_errors = checker.validate_activities(activities)
    if validation_errors:
        return {
            "valid": False,
            "validation_errors": validation_errors
        }
    
    # Check all types of conflicts
    internal_conflicts = checker.check_single_timetable_conflicts(activities)
    cross_timetable_conflicts = checker.check_cross_timetable_conflicts(
        activities, 
        timetable_id
    )
    
    return {
        "valid": not (internal_conflicts or cross_timetable_conflicts),
        "internal_conflicts": internal_conflicts,
        "cross_timetable_conflicts": cross_timetable_conflicts
    }


def clean_mongo_documents(doc):
    if isinstance(doc, list):
        return [clean_mongo_documents(item) for item in doc]
    if isinstance(doc, dict):
        return {key: clean_mongo_documents(value) for key, value in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc

def store_latest_score(score):
    db["settings"].update_one(
        {"option": "latest_score"},
        {"$set": {"value": score}},
        upsert=True
    )
    db["old_scores"].insert_one({"value": score})

@router.get("/available-spaces")
async def get_available_spaces(
    algorithm: str = Query(..., description="Algorithm name"),
    day: str = Query(..., description="Day name"),
    periods: str = Query(..., description="Comma-separated list of period names"),
    exclude_session_id: str = Query(None, description="Optional session ID to exclude from conflict checking"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get available spaces (rooms) for a specific day and period combination.
    Filters out spaces that are already occupied in any timetable for the given algorithm.
    This checks across all semesters for the specific algorithm to ensure no conflicts.
    """
    try:
        # Convert periods string to list
        period_list = periods.split(',')
        
        # Get all timetables for the specified algorithm
        timetables = list(db["Timetable"].find({"algorithm": algorithm}))
        
        # Get all activities across all semesters for this algorithm
        all_activities = []
        for tt in timetables:
            all_activities.extend(tt.get("timetable", []))
        
        # Find occupied spaces for the specified day and periods
        occupied_spaces = set()
        for activity in all_activities:
            # Skip the session we're currently editing if provided
            if exclude_session_id and activity.get("session_id") == exclude_session_id:
                continue
                
            # Get the activity's day name, handling both string and object formats
            activity_day = None
            if isinstance(activity.get("day"), dict):
                activity_day = activity.get("day", {}).get("name")
            else:
                activity_day = activity.get("day")
                
            # Check if the activity is on the requested day
            if activity_day == day:
                # Get the periods for this activity
                activity_periods = []
                for p in activity.get("period", []):
                    # Handle both dictionary format and string format
                    if isinstance(p, dict):
                        period_name = p.get("name")
                        if period_name:
                            activity_periods.append(period_name)
                    elif isinstance(p, str):
                        activity_periods.append(p)
               
                # Check if any of the requested periods overlap with this activity's periods
                if any(period in activity_periods for period in period_list):
                    # This space is occupied during at least one of the requested periods
                    room_name = None
                    if isinstance(activity.get("room"), dict):
                        room_name = activity.get("room", {}).get("name")
                    elif isinstance(activity.get("room"), str):
                        room_name = activity.get("room")
                        
                    if room_name:
                        occupied_spaces.add(room_name)
        
        # Get all spaces from the database
        all_spaces = list(db["Spaces"].find())

        if not all_spaces:
            print("Warning: No spaces found in database")
            return {
                "available_spaces": [],
                "occupied_spaces": list(occupied_spaces),
                "error": "No spaces found in database"
            }
        
        # Filter to only include available spaces
        available_spaces = [
            clean_mongo_documents(space) 
            for space in all_spaces 
            if space.get("name") not in occupied_spaces
        ]
        
        return {
            "available_spaces": available_spaces,
            "occupied_spaces": list(occupied_spaces)
        }
    except Exception as e:
        print(f"Error in get_available_spaces: {str(e)}")
        return {"error": str(e), "available_spaces": [], "occupied_spaces": []}

def extract_specialization_from_subgroup(subgroup):
    """
    Extract specialization from subgroup string like 'Y1S1.SE.1' -> 'SE'
    """
    if not subgroup or not isinstance(subgroup, str):
        return None
        
    parts = subgroup.split('.')
    if len(parts) >= 2:
        return parts[1]  # The second part should be the specialization (IT, SE, CS, etc.)
    
    return None

@router.get("/published/student-year-group/{year_group}")
async def get_student_year_group_timetable(
    year_group: str, 
    specialization: str = Query(None, description="Student specialization (IT, SE, CS, etc.)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get the published timetable entries for a specific year_group and specialization.
    This endpoint is used when a student has their year_group set.
    """
    try:
        # Verify the user is a student
        if current_user.get("role") != "student":
            raise HTTPException(status_code=403, detail="Access denied. Only student users can access this endpoint.")
            
        # Check if we have a published timetable
        published_info = db["settings"].find_one({"option": "published_algorithm"})
        if not published_info:
            return {
                "year_group": year_group,
                "specialization": specialization,
                "entries": [],
                "message": "No published timetable available yet"
            }
        
        algorithm = published_info["value"]
        
        # Get the semester from the year_group (typically Y1S1 format)
        # Extract the first part before any dots (e.g., Y1S1.IT.1 -> Y1S1)
        semester_code = year_group.split('.')[0] if '.' in year_group else year_group
        
        # If specialization is not provided but the year_group contains it, extract it
        if not specialization and '.' in year_group:
            specialization = extract_specialization_from_subgroup(year_group)
            print(f"Extracted specialization from year_group: {specialization}")
        
        # Map it to our semester format
        semester = map_subgroup_to_semester(semester_code)
        if not semester:
            return {
                "year_group": year_group,
                "specialization": specialization,
                "entries": [],
                "message": f"Could not map year_group {year_group} to a semester"
            }
            
        # Find the timetable for the specified semester
        timetable = db["Timetable"].find_one({
            "semester": semester,
            "algorithm": algorithm
        })
        
        if not timetable:
            return {
                "year_group": year_group,
                "specialization": specialization,
                "semester": semester,
                "entries": [],
                "message": f"No timetable found for semester {semester}"
            }
            
        # Get the class number from year_group (e.g., "3" from "Y1S1.IT.3")
        class_number = None
        if year_group.count('.') >= 2:
            parts = year_group.split('.')
            if len(parts) >= 3:
                class_number = parts[2]
        
        # Filter entries for this year_group and specialization
        all_entries = timetable.get("timetable", [])
        filtered_entries = []
        
        # For debugging
        print(f"Filtering for year_group: {year_group}, specialization: {specialization}, class_number: {class_number}")
        
        for entry in all_entries:
            # Case 1: Entry has multiple subgroups (array)
            if isinstance(entry.get("subgroup"), list):
                # First priority: Exact match with student's year_group
                if year_group in entry["subgroup"]:
                    filtered_entries.append(entry)
                    continue
                    
                # Second priority: Common activities for the entire semester (Y1S1)
                if semester_code in entry["subgroup"]:
                    filtered_entries.append(entry)
                    continue
                
                # Third priority: Common activities for the specialization (Y1S1.IT)
                if specialization and any(
                    sg.startswith(f"{semester_code}.{specialization}") and 
                    (not "." in sg.replace(f"{semester_code}.{specialization}", "", 1) or
                     sg.endswith(f".{class_number}"))
                    for sg in entry["subgroup"]
                ):
                    filtered_entries.append(entry)
                    continue
                    
                # Skip entries for other class numbers in the same specialization
                skip = False
                if class_number and specialization:
                    for sg in entry["subgroup"]:
                        parts = sg.split('.')
                        if (len(parts) >= 3 and 
                            parts[0] == semester_code and 
                            parts[1] == specialization and 
                            parts[2] != class_number):
                            skip = True
                            break
                    if skip:
                        continue
            
            # Case 2: Entry has a single subgroup string
            elif isinstance(entry.get("subgroup"), str):
                subgroup = entry.get("subgroup")
                
                # First priority: Exact match with year_group
                if subgroup == year_group:
                    filtered_entries.append(entry)
                    continue
                    
                # Second priority: Common activities for the entire semester
                if subgroup == semester_code:
                    filtered_entries.append(entry)
                    continue
                    
                # Third priority: Common activities for the specialization 
                if specialization and subgroup == f"{semester_code}.{specialization}":
                    filtered_entries.append(entry)
                    continue
                    
                # Skip entries for other class numbers in the same specialization
                if class_number and specialization:
                    parts = subgroup.split('.')
                    if (len(parts) >= 3 and 
                        parts[0] == semester_code and 
                        parts[1] == specialization and 
                        parts[2] != class_number):
                        continue
        
        print(f"Found {len(filtered_entries)} matching entries")
                
        return {
            "year_group": year_group,
            "specialization": specialization,
            "semester": semester,
            "algorithm": algorithm,
            "entries": clean_mongo_documents(filtered_entries)
        }
        
    except Exception as e:
        print(f"Error fetching year_group timetable: {str(e)}")
        return {
            "year_group": year_group,
            "specialization": specialization,
            "entries": [],
            "message": f"Error fetching timetable: {str(e)}"
        }

@router.get("/student-info-validate")
async def validate_student_info(current_user: dict = Depends(get_current_user)):
    """
    Validate the current student user's information and return complete student details.
    This endpoint is specifically for students to verify their profile is complete.
    """
    try:
        # Check if the user has the student role
        if current_user.get("role") != "student":
            raise HTTPException(status_code=403, detail="Access denied. Only student users can use this endpoint.")
        
        # Get the student information from the database
        student = db["Users"].find_one({"id": current_user.get("id")})
        if not student:
            return {
                "valid": False,
                "message": "Student profile not found",
                "student_info": None
            }
        
        # Clean the student document (remove MongoDB IDs)
        student_info = clean_mongo_documents(student)
        
        # Extract specialization from year_group if it's not explicitly set
        if not student_info.get("specialization") and student_info.get("year_group"):
            student_info["specialization"] = extract_specialization_from_subgroup(student_info.get("year_group"))
            
        # Check if required fields are present
        required_fields = ["subgroup", "year_group", "subjects"]
        missing_fields = [field for field in required_fields if not student_info.get(field)]
        
        if missing_fields:
            return {
                "valid": False,
                "message": f"Student profile incomplete. Missing: {', '.join(missing_fields)}",
                "student_info": student_info
            }
        
        # If we get here, all required fields are present
        return {
            "valid": True,
            "message": "Student profile is complete",
            "student_info": student_info
        }
    
    except Exception as e:
        print(f"Error in validate_student_info: {str(e)}")
        return {
            "valid": False,
            "message": f"Error validating student information: {str(e)}",
            "student_info": None
        }

@router.post("/publish")
async def publish_timetable(
    algorithm: str = Query(..., description="Algorithm name to publish"),
    current_user: dict = Depends(get_current_user)
):
    """
    Publish a timetable generated by the specified algorithm.
    This marks the algorithm as the official published timetable that students and staff will see.
    """
    try:
        # Check if user has admin privileges
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Only administrators can publish timetables")
        
        # Check if the algorithm exists and has generated timetables
        timetables = list(db["Timetable"].find({"algorithm": algorithm}))
        if not timetables:
            raise HTTPException(
                status_code=404, 
                detail=f"No timetables found for algorithm {algorithm}"
            )
        
        # Update the published_algorithm setting in the database
        result = db["settings"].update_one(
            {"option": "published_algorithm"},
            {"$set": {"value": algorithm}},
            upsert=True  # Create if it doesn't exist
        )
        
        # Send a notification to all users
        db["notifications"].insert_many([
            {
                "message": f"New timetable has been published using {algorithm}",
                "type": "info",
                "read": False,
                "recipient": "all",  # Special recipient ID to indicate all users
                "created_at": datetime.now()
            },
            {
                "message": f"You have published the {algorithm} timetable",
                "type": "success",
                "read": False,
                "recipient": current_user["id"],
                "created_at": datetime.now()
            }
        ])
        
        return {
            "success": True,
            "message": f"Successfully published timetable using algorithm {algorithm}",
            "algorithm": algorithm,
            "updated": result.modified_count > 0,
            "created": result.upserted_id is not None
        }
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error publishing timetable: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish timetable: {str(e)}"
        )

@router.get("/published")
async def get_published_timetable(current_user: dict = Depends(get_current_user)):
    """
    Get information about the currently published timetable.
    """
    try:
        # Check if we have a published timetable
        published_info = db["settings"].find_one({"option": "published_algorithm"})
        if not published_info:
            return {
                "published": False,
                "message": "No timetable has been published yet"
            }
        
        algorithm = published_info["value"]
        
        # Get basic information about all timetables for this algorithm
        timetables = list(db["Timetable"].find(
            {"algorithm": algorithm}, 
            {"semester": 1, "code": 1}
        ))
        
        return {
            "published": True,
            "algorithm": algorithm,
            "timetables": clean_mongo_documents(timetables),
            "published_at": published_info.get("updated_at", None)
        }
        
    except Exception as e:
        print(f"Error getting published timetable: {str(e)}")
        return {
            "published": False,
            "message": f"Error: {str(e)}"
        }

@router.get("/published/faculty/{faculty_id}")
async def get_faculty_timetable(
    faculty_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the published timetable entries for a specific faculty member.
    This endpoint retrieves all classes where this faculty is assigned as the teacher.
    """
    try:
        # Verify the user is authorized to view this faculty's timetable
        if current_user.get("role") != "admin" and current_user.get("id") != faculty_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only view your own timetable.")
            
        # Check if we have a published timetable
        published_info = db["settings"].find_one({"option": "published_algorithm"})
        if not published_info:
            return {
                "faculty_id": faculty_id,
                "entries": [],
                "message": "No published timetable available yet"
            }
        
        algorithm = published_info["value"]
        
        # Get all timetables for this algorithm
        timetables = list(db["Timetable"].find({"algorithm": algorithm}))
        
        # Filter entries for this faculty_id across all timetables
        faculty_entries = []
        
        for timetable in timetables:
            for entry in timetable.get("timetable", []):
                # Match entries where this faculty is the teacher
                if entry.get("teacher") == faculty_id:
                    # Add semester info and timetable_id to the entry for context
                    entry_with_semester = {
                        **entry,
                        "semester": timetable.get("semester"),
                        "timetable_id": str(timetable.get("_id"))  # Include timetable ID
                    }
                    faculty_entries.append(entry_with_semester)
        
        # Get faculty details
        faculty = db["Users"].find_one({"id": faculty_id})
        
        if not faculty:
            return {
                "faculty_id": faculty_id,
                "entries": clean_mongo_documents(faculty_entries),
                "message": "Faculty details not found, but timetable entries retrieved"
            }
            
        return {
            "faculty_id": faculty_id,
            "faculty_name": f"{faculty.get('first_name', '')} {faculty.get('last_name', '')}",
            "faculty_position": faculty.get('position', ''),
            "algorithm": algorithm,
            "entries": clean_mongo_documents(faculty_entries)
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions with their status codes
        raise
    except Exception as e:
        print(f"Error fetching faculty timetable: {str(e)}")
        return {
            "faculty_id": faculty_id,
            "entries": [],
            "message": f"Error fetching timetable: {str(e)}"
        }

@router.get("/faculty-info-validate")
async def validate_faculty_info(current_user: dict = Depends(get_current_user)):
    """
    Validate the faculty member's information and return complete faculty details.
    This endpoint is specifically for faculty members to verify their profile is complete.
    """
    try:
        # Check if the user has permission to access this faculty's information
        if current_user.get("role") != "faculty":
            raise HTTPException(status_code=403, detail="Access denied. You can only validate your own information.")
        
        # Get the faculty information from the database
        faculty = db["Users"].find_one({"id": current_user.get("id")})
        if not faculty:
            return {
                "valid": False,
                "message": "Faculty profile not found",
                "faculty_info": None
            }
        
        # Clean the faculty document (remove MongoDB IDs)
        faculty_info = clean_mongo_documents(faculty)
        
        # Check if required fields are present
        required_fields = ["position", "subjects"]
        missing_fields = [field for field in required_fields if not faculty_info.get(field)]
        
        if missing_fields:
            return {
                "valid": False,
                "message": f"Faculty profile incomplete. Missing: {', '.join(missing_fields)}",
                "faculty_info": faculty_info
            }
        
        # If we get here, all required fields are present
        return {
            "valid": True,
            "message": "Faculty profile is complete",
            "faculty_info": {
                "id": faculty_info.get("id"),
                "name": f"{faculty_info.get('first_name', '')} {faculty_info.get('last_name', '')}",
                "position": faculty_info.get("position"),
                "phone" : faculty_info.get("telephone"),
                "email" : faculty_info.get("email"),
                "subjects": faculty_info.get("subjects"),
            }
        }
    
    except Exception as e:
        print(f"Error in validate_faculty_info: {str(e)}")
        return {
            "valid": False,
            "message": f"Error validating faculty information: {str(e)}",
            "faculty_info": None
        }

@router.post("/faculty/request-change")
async def request_timetable_change(
    request_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Submit a request from faculty to change something in their timetable.
    This creates a pending request that admins can approve or reject.
    """
    try:
        # Verify the user is a faculty member
        if current_user.get("role") != "faculty":
            raise HTTPException(status_code=403, detail="Access denied. Only faculty can submit change requests.")
        
        # Validate request data
        required_fields = ["type", "session_id", "reason"]
        missing_fields = [field for field in required_fields if not request_data.get(field)]
        
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Get faculty info
        faculty = db["Users"].find_one({"id": current_user.get("id")})
        if not faculty:
            raise HTTPException(status_code=404, detail="Faculty profile not found")
        
        # Create a new request record
        request_id = ObjectId()
        new_request = {
            "_id": request_id,
            "faculty_id": current_user.get("id"),
            "faculty_name": f"{faculty.get('first_name', '')} {faculty.get('last_name', '')}",
            "type": request_data.get("type"),
            "session_id": request_data.get("session_id"),
            "timetable_id": request_data.get("timetable_id"),
            "reason": request_data.get("reason"),
            "status": "pending",
            "submitted_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        # Add type-specific fields
        if request_data.get("type") == "substitute":
            new_request["substitute_id"] = request_data.get("substitute")
            # Get substitute teacher name
            substitute = db["Users"].find_one({"id": request_data.get("substitute")})
            if substitute:
                new_request["substitute_name"] = f"{substitute.get('first_name', '')} {substitute.get('last_name', '')}"
        elif request_data.get("type") == "roomChange":
            # Add room change specific fields
            new_request["new_room"] = request_data.get("new_room")
            # Include room ID if provided
            if "room_id" in request_data:
                new_request["room_id"] = request_data.get("room_id")
            # Include full room details if provided
            if "room_details" in request_data:
                new_request["room_details"] = request_data.get("room_details")
        elif request_data.get("type") == "timeChange":
            # Add time change specific fields
            if "new_day" in request_data:
                new_request["new_day"] = request_data.get("new_day")
            if "new_periods" in request_data:
                new_request["new_periods"] = request_data.get("new_periods")
            # Handle optional room change with time change
            if "new_room" in request_data:
                new_request["new_room"] = request_data.get("new_room")
                if "room_id" in request_data:
                    new_request["room_id"] = request_data.get("room_id")
                if "room_details" in request_data:
                    new_request["room_details"] = request_data.get("room_details")
        
        # Insert the request
        db["timetable_change_requests"].insert_one(new_request)
        
        # Create notification for admin
        db["notifications"].insert_one({
            "message": f"New timetable change request from {faculty.get('first_name')} {faculty.get('last_name')}",
            "type": "info",
            "read": False,
            "recipient": "admin",  # For all admins
            "created_at": datetime.now()
        })
        
        return {
            "success": True,
            "message": "Request submitted successfully",
            "request_id": str(request_id)
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error submitting timetable change request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit request: {str(e)}"
        )

@router.get("/faculty/change-requests")
async def get_faculty_change_requests(
    current_user: dict = Depends(get_current_user)
):
    """
    Get all change requests submitted by the current faculty member
    """
    try:
        # Verify the user is a faculty member
        if current_user.get("role") != "faculty":
            raise HTTPException(status_code=403, detail="Access denied. Only faculty can view their requests.")
        
        # Get all requests for this faculty member
        requests = list(db["timetable_change_requests"].find(
            {"faculty_id": current_user.get("id")}
        ).sort("submitted_at", -1))  # Most recent first
        
        return {
            "requests": clean_mongo_documents(requests)
        }
        
    except Exception as e:
        print(f"Error getting faculty change requests: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get requests: {str(e)}"
        )

@router.get("/admin/change-requests")
async def get_admin_change_requests(
    status: str = Query(None, description="Filter by status (pending, approved, rejected)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all timetable change requests for admin to review
    """
    try:
        # Verify the user is an admin
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied. Only admins can view all requests.")
        
        # Build query filter
        filter_query = {}
        if status:
            filter_query["status"] = status
        
        # Get all requests
        requests = list(db["timetable_change_requests"].find(
            filter_query
        ).sort("submitted_at", -1))  # Most recent first
        
        return {
            "requests": clean_mongo_documents(requests)
        }
        
    except Exception as e:
        print(f"Error getting admin change requests: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get requests: {str(e)}"
        )

@router.put("/admin/change-requests/{request_id}")
async def update_change_request_status(
    request_id: str,
    update_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the status of a timetable change request (approve/reject)
    With improved conflict checking for approvals
    """
    try:
        # Verify the user is an admin
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access denied. Only admins can update request status.")
        
        # Validate update data
        if "status" not in update_data or update_data["status"] not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="Invalid status. Must be 'approved' or 'rejected'.")
        
        # Get the request
        request = db["timetable_change_requests"].find_one({"_id": ObjectId(request_id)})
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Update the request status in database
        db["timetable_change_requests"].update_one(
            {"_id": ObjectId(request_id)},
            {
                "$set": {
                    "status": update_data["status"],
                    "admin_comments": update_data.get("admin_comments", ""),
                    "updated_at": datetime.now(),
                    "updated_by": current_user.get("id")
                }
            }
        )
        
        # If approved, implement the requested changes with conflict checking
        conflicts = []
        if update_data["status"] == "approved":
            conflicts = await implement_timetable_change(request, current_user)
            
            # If conflicts were detected
            if conflicts:
                # Revert the status to pending
                db["timetable_change_requests"].update_one(
                    {"_id": ObjectId(request_id)},
                    {
                        "$set": {
                            "status": "pending",
                            "admin_comments": update_data.get("admin_comments", "") + 
                                             "\n[System] Conflicts detected. Changes not applied.",
                            "updated_at": datetime.now(),
                        }
                    }
                )
                
                # Return conflicts to frontend
                return {
                    "success": False,
                    "message": "Changes could not be applied due to conflicts",
                    "conflicts": conflicts
                }
        
        # Create notification for faculty
        db["notifications"].insert_one({
            "message": f"Your timetable change request has been {update_data['status']}",
            "type": "info" if update_data["status"] == "approved" else "warning",
            "read": False,
            "recipient": request["faculty_id"],
            "created_at": datetime.now()
        })
        
        return {
            "success": True,
            "message": f"Request {update_data['status']} successfully"
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"Error updating change request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update request: {str(e)}"
        )

async def implement_timetable_change(request, current_user):
    """
    Implement the changes requested in an approved request
    Returns a list of conflicts if any are detected
    """
    try:
        # Get the published algorithm
        published_info = db["settings"].find_one({"option": "published_algorithm"})
        if not published_info:
            raise Exception("No published timetable available")
        
        algorithm = published_info["value"]
        
        # Find which timetable contains the session
        timetables = list(db["Timetable"].find({"algorithm": algorithm}))
        target_timetable = None
        entry_index = None
        target_entry = None
        for timetable in timetables:
            for i, entry in enumerate(timetable.get("timetable", [])):
                if entry.get("session_id") == request["session_id"]:
                    target_timetable = timetable
                    entry_index = i
                    target_entry = entry
                    break
            if target_timetable:
                break
        
        if not target_timetable or entry_index is None:
            raise Exception(f"Session {request['session_id']} not found in any timetable")
        
        # Make changes based on request type
        updated_entry = dict(target_entry)  # Create a copy
        if request["type"] == "substitute":
            # Update teacher to substitute
            updated_entry["original_teacher"] = updated_entry.get("teacher")
            updated_entry["teacher"] = request.get("substitute_id")
            updated_entry["is_substitute"] = True
        elif request["type"] == "roomChange":
            # Update room with the requested new room
            if "new_room" in request:
                # Check if we have detailed room info in the request
                if "room_details" in request:
                    updated_entry["room"] = request["room_details"]
                else:
                    # Get the new room details from the database
                    room_details = None
                    # Try using room_id if available
                    if "room_id" in request:
                        room_details = db["Spaces"].find_one({"_id": ObjectId(request["room_id"])})
                    # Fallback to looking up by name
                    if not room_details:
                        room_details = db["Spaces"].find_one({"name": request["new_room"]})
                    if room_details:
                        updated_entry["room"] = {
                            "_id": room_details.get("_id"),
                            "name": room_details.get("name"),
                            "long_name": room_details.get("long_name"),
                            "code": room_details.get("code"),
                            "capacity": room_details.get("capacity")
                        }
                    else:
                        # If room details not found, just use the name
                        updated_entry["room"] = request["new_room"]
        elif request["type"] == "timeChange":
            # Update day and periods
            if "new_day" in request:
                # Get the day details from the database
                day_details = db["Days"].find_one({"name": request["new_day"]})
                if day_details:
                    updated_entry["day"] = {
                        "_id": day_details.get("_id"),
                        "name": day_details.get("name"),
                        "long_name": day_details.get("long_name")
                    }
                else:
                    # If day details not found, just use the name
                    updated_entry["day"] = request["new_day"]
            if "new_periods" in request and isinstance(request["new_periods"], list):
                # Get period details from the database
                period_objects = []
                for period_name in request["new_periods"]:
                    period_details = db["Periods"].find_one({"name": period_name})
                    if period_details:
                        period_objects.append({
                            "_id": period_details.get("_id"),
                            "name": period_details.get("name"),
                            "long_name": period_details.get("long_name"),
                            "is_interval": period_details.get("is_interval", False),
                            "created_at": period_details.get("created_at"),
                            "updated_at": period_details.get("updated_at"),
                            "index": period_details.get("index", 0)
                        })
                    else:
                        # If period details not found, just use the name
                        period_objects.append({"name": period_name})
                
                # Sort periods by index to maintain correct order
                period_objects.sort(key=lambda p: p.get("index", 0) if isinstance(p, dict) else 0)
                
                updated_entry["period"] = period_objects
                # Update duration if needed
                if len(period_objects) != updated_entry.get("duration", 0):
                    updated_entry["duration"] = len(period_objects)
            # Update room if provided (optional for time changes)
            if "new_room" in request:
                # Check if we have detailed room info in the request
                if "room_details" in request:
                    updated_entry["room"] = request["room_details"]
                else:
                    # Try using room_id if available
                    room_details = None
                    if "room_id" in request:
                        room_details = db["Spaces"].find_one({"_id": ObjectId(request["room_id"])})
                    # Fallback to looking up by name
                    if not room_details:
                        room_details = db["Spaces"].find_one({"name": request["new_room"]})
                    if room_details:
                        updated_entry["room"] = {
                            "_id": room_details.get("_id"),
                            "name": room_details.get("name"),
                            "long_name": room_details.get("long_name"),
                            "code": room_details.get("code"),
                            "capacity": room_details.get("capacity")
                        }
                    else:
                        # If room details not found, just use the name
                        updated_entry["room"] = request["new_room"]
        
        # Check for conflicts before applying changes
        checker = ConflictChecker(db)
        conflicts_internal = checker.check_single_timetable_conflicts(
            target_timetable["_id"], 
            [updated_entry], 
            request["session_id"]
        )
        # Check for cross-timetable conflicts
        algorithm = target_timetable.get("algorithm", "")
        conflicts_cross = checker.check_cross_timetable_conflicts(
            [updated_entry], 
            target_timetable["_id"], 
            algorithm
        )
        
        all_conflicts = conflicts_internal + conflicts_cross
        
        if all_conflicts:
            # If conflicts exist, return them without updating
            return all_conflicts
        
        # No conflicts, update the timetable
        timetable_entries = target_timetable.get("timetable", [])
        timetable_entries[entry_index] = updated_entry
        
        # db["Timetable"].update_one(
        #     {"_id": target_timetable["_id"]},
        #     {"$set": {"timetable": timetable_entries}}
        # )
        
        # Log the change
        db["timetable_change_log"].insert_one({
            "request_id": request["_id"],
            "timetable_id": target_timetable["_id"],
            "session_id": request["session_id"],
            "change_type": request["type"],
            "before": target_entry,
            "after": updated_entry,
            "changed_by": current_user["id"],
            "changed_at": datetime.now()
        })
        
        return []  # Return empty list indicating no conflicts
        
    except Exception as e:
        print(f"Error implementing timetable change: {str(e)}")
        # Log the error for debugging
        db["error_log"].insert_one({
            "error": str(e),
            "context": "implement_timetable_change",
            "request_id": request["_id"],
            "timestamp": datetime.now()
        })
        # Return a generic conflict
        return [{
            "type": "error",
            "description": f"Error implementing change: {str(e)}",
            "activities": []
        }]

