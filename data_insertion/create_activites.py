import json
import random
import os 
def generate_activity_code(index):
    return f"AC-{index:03d}"

def find_teachers_for_subject(
    subject_code,
    teachers,
    positions,
    max_teachers,
    current_activities,
    new_activity_duration
):
    """
    Try to find up to `max_teachers` teacher IDs who:
      1) Teach the given subject_code,
      2) Have a position in `positions`,
      3) Are within their target hours if assigned new_activity_duration more hours.

    If none qualify under target hours, fallback to the least-loaded teachers among those
    who can teach the subject & hold the positions, but may exceed target hours.

    If there is truly no teacher who can handle subject_code + positions at all, 
    try with any teacher who can teach the subject regardless of position.
    """
    if current_activities is None:
        current_activities = []
    
    under_target_teachers = []
    fallback_teachers = []
    any_position_teachers = [] # New list for teachers of any position

    # Track whether *any* teacher can teach this subject+position
    can_teach_this_subject = False

    for teacher in teachers:
        # Check if the teacher can teach this subject
        if subject_code in teacher["subjects"]:
            has_valid_position = any(pos in positions for pos in [teacher["position"]])
            
            # Calculate how many hours they've already been assigned
            current_hours = sum(
                act["duration"]
                for act in current_activities
                if act.get("teacher_ids") and teacher["id"] in act["teacher_ids"]
            )
            
            # For teachers with the preferred position
            if has_valid_position:
                can_teach_this_subject = True
                if current_hours + new_activity_duration <= teacher["target_hours"]:
                    under_target_teachers.append((teacher["id"], current_hours))
                else:
                    fallback_teachers.append((teacher["id"], current_hours))
            # For any teacher regardless of position
            else:
                if current_hours + new_activity_duration <= teacher["target_hours"]:
                    any_position_teachers.append((teacher["id"], current_hours))
                    
    # Sort by ascending workload
    under_target_teachers.sort(key=lambda x: x[1])
    fallback_teachers.sort(key=lambda x: x[1])
    any_position_teachers.sort(key=lambda x: x[1])

    # Take the necessary number of teachers, prioritizing those under target hours
    chosen_teachers = [t[0] for t in under_target_teachers[:max_teachers]]
    
    # If we don't have enough under-target teachers, add from fallback list
    remaining_slots = max_teachers - len(chosen_teachers)
    if remaining_slots > 0 and fallback_teachers:
        fallback_chosen = [t[0] for t in fallback_teachers[:remaining_slots]]
        chosen_teachers.extend(fallback_chosen)
        print(
            f"WARNING: Assigned teacher(s) {fallback_chosen} to subject {subject_code} "
            "but this likely exceeds their target hours."
        )
    
    # If we still don't have enough teachers, try any position as a last resort
    remaining_slots = max_teachers - len(chosen_teachers)
    if remaining_slots > 0 and any_position_teachers:
        any_pos_chosen = [t[0] for t in any_position_teachers[:remaining_slots]]
        chosen_teachers.extend(any_pos_chosen)
        print(
            f"WARNING: Assigned teacher(s) {any_pos_chosen} to subject {subject_code} "
            f"who don't have the preferred positions {positions}."
        )
    
    # If we still have no one, raise error
    if not chosen_teachers:
        raise RuntimeError(
            f"CRITICAL ERROR: No teachers available for subject {subject_code} "
            "with any position who can teach this subject!"
        )

    return chosen_teachers


def get_subgroup_counts(students_file):
    """
    Count how many students exist for each combination of:
      (year, subgroup, specialization, attend_days).
    """
    with open(students_file, 'r') as sf:
        students = json.load(sf)
    
    subgroup_counts = {}
    for student in students:
        key = (
            student["year"],
            student["subgroup"],
            tuple(student["specialization"]),
            student["attend_days"]
        )
        subgroup_counts[key] = subgroup_counts.get(key, 0) + 1

    print("Subgroup counts (for debugging):")
    print(subgroup_counts)
    return subgroup_counts


def generate_activities(modules_file, teachers_file, students_file, output_file):
    """
    Generates a list of activities where:
      - Lecture and Tutorial are combined into a single activity
      - Lab remains separate (if the module has_lab = True)

    This approach reduces the total number of separate activities,
    which can help distribute teacher workloads more simply.
    """
    with open(modules_file, 'r') as mf:
        modules = json.load(mf)

    with open(teachers_file, 'r') as tf:
        teachers = json.load(tf)

    # Count how many students exist for each (year, subgroup, specialization, days)
    subgroup_counts = get_subgroup_counts(students_file)

    activities = []
    activity_index = 1

    # Track assignment failures for reporting at the end
    position_fallbacks = []
    
    # Iterate over each module
    for module in modules:
        semester = module["semester"]
        subject = module["code"]
        year = int(semester[1])  # "Y2S1" -> year=2
        lecture_hours = module["lecture_hours"]
        tutorial_hours = module["tutorial_hours"]
        lab_hours = module["lab_hours"]
        has_lab = module.get("has_lab", False)

        # We combine Lecture + Tutorial hours
        combined_lt_hours = lecture_hours + tutorial_hours

        # Specializations (e.g. ["IT", "SE"]) or just a single string
        module_specializations = module.get("specialization", [])
        if isinstance(module_specializations, str):
            module_specializations = [module_specializations]
        if not module_specializations:
            # If no specialization is listed, use an empty placeholder
            module_specializations = [""]

        for spec in module_specializations:
            spec_chars = list(spec) if spec else []

            # Calculate how many students match
            relevant_count = 0
            for key, count in subgroup_counts.items():
                student_year, student_subgroup, student_spec_tuple, _days = key

                # Must match year exactly
                if student_year != year:
                    continue

                # Check semester (some have Y2S1, Y2S1/2, etc.)
                if (semester not in student_subgroup) and (student_subgroup not in semester):
                    continue

                # If spec is "IT", then each char 'I','T' must be in student's specialization
                if all(ch in student_spec_tuple for ch in spec_chars):
                    relevant_count += count
            
            # If 0, assume at least 40 so we get at least 2 groups
            if relevant_count == 0:
                relevant_count = 40

            num_groups = (relevant_count + 39) // 40
            num_groups = max(2, num_groups)

            # Build subgroup IDs, e.g. "Y1S1.IT.1", "Y1S1.IT.2", ...
            subgroup_prefix = f"Y{year}{semester[2:]}"
            if spec:
                subgroup_ids = [
                    f"{subgroup_prefix}.{spec}.{i}" for i in range(1, num_groups + 1)
                ]
            else:
                subgroup_ids = [
                    f"{subgroup_prefix}.{i}" for i in range(1, num_groups + 1)
                ]

            print(
                f"Module {subject}, specialization '{spec}', student count = {relevant_count}, "
                f"subgroups = {num_groups}"
            )

            # --- SINGLE Lecture+Tutorial Activity ---
            try:
                combined_lt_teachers = find_teachers_for_subject(
                    subject_code=subject,
                    teachers=teachers,
                    positions=["Professor", "Senior Lecturer", "Lecturer"],
                    max_teachers=1,  # single teacher for the combined block
                    current_activities=activities,
                    new_activity_duration=combined_lt_hours
                )

                combined_lt_activity = {
                    "code": generate_activity_code(activity_index),
                    "name": (
                        f"{module['long_name']}"
                        f"{(' (' + spec + ')') if spec else ''}"
                        " Lecture+Tutorial"
                    ),
                    "subject": subject,
                    "teacher_ids": combined_lt_teachers,
                    "subgroup_ids": subgroup_ids,
                    "duration": combined_lt_hours,
                    "type": "Lecture+Tutorial",  # Custom label
                    "space_requirements": ["Lecture Hall"]
                }
                activities.append(combined_lt_activity)
                activity_index += 1
            except RuntimeError as e:
                print(f"ERROR creating Lecture+Tutorial activity for {subject}: {e}")
                position_fallbacks.append(f"Module {subject}: {e}")

            # --- LAB Activity (modified to be more flexible) ---
            if has_lab:
                try:
                    lab_teachers = find_teachers_for_subject(
                        subject_code=subject,
                        teachers=teachers,
                        positions=["Lecturer", "Instructor", "Senior Lecturer", "Professor"],  # More flexible positions
                        max_teachers=2,
                        current_activities=activities,
                        new_activity_duration=lab_hours
                    )
                    lab_activity = {
                        "code": generate_activity_code(activity_index),
                        "name": (
                            f"{module['long_name']}"
                            f"{(' (' + spec + ')') if spec else ''}"
                            " Lab"
                        ),
                        "subject": subject,
                        "teacher_ids": lab_teachers,
                        "subgroup_ids": subgroup_ids,
                        "duration": lab_hours,
                        "type": "Lab",
                        "space_requirements": ["Lab Room"]
                    }
                    activities.append(lab_activity)
                    activity_index += 1
                except RuntimeError as e:
                    print(f"ERROR creating Lab activity for {subject}: {e}")
                    position_fallbacks.append(f"Module {subject} Lab: {e}")

    # Report summary of any position fallbacks that happened
    if position_fallbacks:
        print("\n========== WARNING: Position Fallback Summary ==========")
        for msg in position_fallbacks:
            print(msg)
        print("========================================================\n")

    # Finally, write the resulting activities to the JSON output
    with open(output_file, 'w') as of:
        json.dump(activities, of, indent=4)

script_dir = os.path.dirname(os.path.abspath(__file__))

# Example usage (you can remove or comment out the lines below if you prefer)
modules_file = os.path.join(script_dir, "modules.json")
teachers_file = os.path.join(script_dir,"updated_teachers.json")
students_file = os.path.join(script_dir,"transformed_students.json")
output_file = os.path.join(script_dir,"activities.json")

generate_activities(modules_file, teachers_file, students_file, output_file)