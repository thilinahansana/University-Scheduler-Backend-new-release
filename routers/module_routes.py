from fastapi import APIRouter, HTTPException, Depends
from models.module_model import Module
from utils.database import db
from typing import List
from routers.user_router import get_current_user

router = APIRouter()


def get_admin_role(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "faculty"]:
        raise HTTPException(status_code=403, detail="You don't have permission to perform this action.")
    return current_user

def get_module_role(current_user: dict = Depends(get_current_user)):
    if current_user["role"] not in ["admin", "faculty" , "student"]:
        raise HTTPException(status_code=403, detail="You don't have permission to perform this action.")
    return current_user

@router.post("/modules", response_model=Module)
async def add_module(module: Module, current_user: dict = Depends(get_admin_role)):
    existing_module = db["modules"].find_one({"code": module.code})
    if existing_module:
        raise HTTPException(status_code=400, detail=f"Module with code {module.code} already exists.")
    
    db["modules"].insert_one(module.dict())
    return module


@router.get("/modules", response_model=List[Module])
async def get_modules(current_user: dict = Depends(get_module_role)):
    modules = list(db["modules"].find())
    return modules


@router.put("/modules/{module_code}", response_model=Module)
async def update_module(module_code: str, module: Module, current_user: dict = Depends(get_admin_role)):
    result = db["modules"].update_one(
        {"code": module_code}, {"$set": module.dict()}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Module with code {module_code} not found.")
    # Fix: Return the updated module instead of all modules
    updated_module = db["modules"].find_one({"code": module_code})
    if not updated_module:
        raise HTTPException(status_code=404, detail=f"Module with code {module_code} not found after update.")
    return updated_module


@router.delete("/modules/{module_code}")
async def delete_module(module_code: str, current_user: dict = Depends(get_admin_role)):
    result = db["modules"].delete_one({"code": module_code})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Module with code {module_code} not found.")
    return {"message": f"Module with code {module_code} deleted successfully"}
