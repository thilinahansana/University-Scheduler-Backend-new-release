from fastapi import FastAPI
from routers import user_router,info_router, faculty_routes, module_routes, year_routes, space_routes, activity_routes, timetable_routes
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

app.include_router(user_router.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(info_router.router, prefix="/api/v1/info", tags=["Info"])
app.include_router(faculty_routes.router, prefix="/api/v1/faculty", tags=["Faculty"])
app.include_router(module_routes.router, prefix="/api/v1/module", tags=["Module"])
app.include_router(year_routes.router, prefix="/api/v1/year", tags=["Year"])
app.include_router(space_routes.router, prefix="/api/v1/space", tags=["Space"])
app.include_router(activity_routes.router, prefix="/api/v1/activity", tags=["Activity"])
app.include_router(timetable_routes.router, prefix="/api/v1/timetable", tags=["Timetable"])


@app.get("/")
async def root():
    return {"message": "Welcome to the TimeTableWhiz"}
