from generator.data_collector import *
from deap import base, creator, tools, algorithms
import random
from deap.algorithms import eaMuCommaLambda

days = []
facilities = []
modules = []
periods = []
students = []
teachers = []
years = []
activities = []

def get_data():
    global days, facilities, modules, periods, students, teachers, years, activities
    days =  get_days()
    facilities =  get_spaces()
    modules =  get_modules()
    periods =  get_periods()
    students =  get_students()
    teachers =  get_teachers()
    years =  get_years()
    activities =  get_activities()

def print_first():
    print(days[0])
    print(facilities[0])
    print(modules[0])
    print(periods[0])
    print(students[0])
    print(teachers[0])
    print(years[0])
    print(activities[0])


creator.create("FitnessMulti", base.Fitness, weights=(-1.0, -1.0, -1.0, -1.0))
creator.create("Individual", list, fitness=creator.FitnessMulti)
toolbox = base.Toolbox()

def get_num_students_per_activity(activity_code):
    module_code = next((activity["subject"] for activity in activities if activity["code"] == activity_code), None)
    if not module_code:
        return 0

    return len([student for student in students if module_code in student["subjects"]])
    

def generate_individual():
    individual = []
    for activity in activities:
        num_of_students = get_num_students_per_activity(activity["code"])
        
        room = random.choice([x for x in facilities if x["capacity"] >= num_of_students])
        
        day = random.choice(days)

        teacher = random.choice(activity["teacher_ids"])
                
        period_start = random.choice(periods[:len(periods) - activity["duration"] - 1])
        
        period = [period_start]
        for i in range(1, activity["duration"]):
            next_period = periods[periods.index(period_start) + i]
            period.append(next_period)
        
        individual.append({
            "subgroup": activity["subgroup_ids"][0],
            "activity_id": activity["code"],
            "day": day,
            "period": period,
            "room": room,
            "teacher": teacher,
            "duration": activity["duration"],
            "subject": activity["subject"]
        })
        
        activity["periods_assigned"] = activity.get("periods_assigned", []) + period
    
    return individual

toolbox.register("individual", tools.initIterate, creator.Individual, generate_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)


def evaluate(individual):
    room_conflicts = 0
    teacher_conflicts = 0
    interval_conflicts = 0
    period_conflicts = 0

    scheduled_activities = {}
    interval_usage = {}

    for schedule in individual:
        key = (schedule["day"]["_id"], schedule["period"][0]["_id"])
        if key not in scheduled_activities:
            scheduled_activities[key] = []
        scheduled_activities[key].append(schedule)
        for per in schedule["period"]:
            if per["is_interval"]:
                interval_usage[per["_id"]] = interval_usage.get(per["_id"], 0) + 1

    for key, scheduled in scheduled_activities.items():
        rooms_used = {}
        teachers_involved = []
        periods_used = {}

        
        for activity in scheduled:
            room = activity["room"]
            if room["code"] in rooms_used:
                rooms_used[room["code"]] += 1
            else:
                rooms_used[room["code"]] = 1

            teachers_involved.append(activity["teacher"])

            for per in activity["period"]:
                periods_used[per["_id"]] = periods_used.get(per["_id"], 0) + 1

        for room, count in rooms_used.items():
            if count > 1: 
                room_conflicts += count - 1

        teacher_conflicts += len(teachers_involved) - len(set(teachers_involved))

    interval_conflicts = sum(interval_usage.values())
    period_conflicts = sum(periods_used.values())

    return teacher_conflicts, room_conflicts, interval_conflicts, period_conflicts




toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxTwoPoint)
toolbox.register("mutate", tools.mutShuffleIndexes, indpb=0.2)
toolbox.register("select", tools.selSPEA2)

def generate_ga():
    get_data()
    print_first()
    
    pop_size = 100
    generations = 30

    pop = toolbox.population(n=pop_size)
    hof = tools.HallOfFame(1)  

    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("teacher_conflicts", lambda fits: min(fit[0] for fit in fits))
    stats.register("room_conflicts", lambda fits: min(fit[1] for fit in fits))
    stats.register("interval_conflicts", lambda fits: min(fit[2] for fit in fits))
    stats.register("period_conflicts", lambda fits: min (fit[3] for fit in fits))

    pop, log = algorithms.eaMuPlusLambda(
        population=pop,
        toolbox=toolbox,
        mu=pop_size,
        lambda_=pop_size,
        cxpb=0.7,
        mutpb=0.2,
        ngen=generations,
        stats=stats,
        halloffame=hof,
        verbose=True,
    )


    li = [x for x in hof[0]]

    return pop, log, hof, li
