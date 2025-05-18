def detect_conflicts(activities):
    conflicts = []
    for i, activity1 in enumerate(activities):
        for j, activity2 in enumerate(activities):
            if i != j and activity1["day"]["name"] == activity2["day"]["name"]:
                periods1 = {period["name"] for period in activity1["period"]}
                periods2 = {period["name"] for period in activity2["period"]}
                if periods1 & periods2:
                    conflicts.append((activity1, activity2))
    return conflicts
