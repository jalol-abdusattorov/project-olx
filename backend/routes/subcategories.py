from datetime import datetime as dt, timezone
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from mongodb import *
from models import SubcategoryRequest
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


# AUTHORIZED & ADMIN
@router.post('/subcategory')
def create_subcategory(
    subcategory: SubcategoryRequest,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        parent_category_id = ObjectId(subcategory.parent_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    name = subcategory.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Subcategory name cannot be empty")

    if subcategory.level < 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid subcategory level"
        )

    # Make sure that the subcategory's parent exists
    if subcategory.level != 1:
        parent = subcategories_collection.find_one({ "_id": parent_category_id })
        if not parent:
            raise HTTPException(status_code=404, detail="Parent subcategory not found")

        if parent.get('level') != subcategory.level - 1:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid level {subcategory.level}. Expected level {parent.get('level') + 1}"
            )
        
        absolute_parent_id = parent['absolute_parent_id']

    else:
        parent = categories_collection.find_one({ "_id": parent_category_id })
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")

        absolute_parent_id = parent['_id']

    # Dont allow duplicate names, but allow, only if they are not in the same level
    subcategory_exists = subcategories_collection.find_one({ "name": name, "parent_id": parent_category_id })
    if subcategory_exists:
        raise HTTPException(status_code=409, detail=f"Subcategory '{name}' already exists")


    new_subcategory = {
        "parent_id": parent_category_id,
        "absolute_parent_id": absolute_parent_id,
        "name": name,
        "level": subcategory.level,
        "created_at": dt.now(timezone.utc)
    }

    subcategory_id = subcategories_collection.insert_one(new_subcategory).inserted_id

    return {
        "ok": True,
        "subcategory_id": str(subcategory_id),
    }


# AUTHORIZED & ADMIN
@router.put('/subcategory/rename')
def rename_subcategory(
    subcategory_id: str,
    name: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="New name can't be empty")

    try:
        s_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    subcategory = subcategories_collection.find_one({ "_id": s_id })
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    if subcategory['name'] == name:
        return {
            "ok": True,
            "subcategory_id": subcategory_id,
            "message": "New name is same as the old name"
        }

    subcategories_collection.update_one({ "_id": s_id }, { "$set": { "name": name } })

    return {
        "ok": True,
        "subcategory_id": subcategory_id,
        "old_name": subcategory['name'],
        "new_name": name
    }


# AUTHORIZED & ADMIN
@router.put('/subcategory/move')
def move_subcategory(
    subcategory_id: str,
    new_parent_id: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        s_id = ObjectId(subcategory_id)
        parent_id = ObjectId(new_parent_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    subcategory = subcategories_collection.find_one({ "_id": s_id })
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    if parent_id == subcategory['parent_id']:
        return {"ok": True, "message": "Nothing changed."}


    parent = subcategories_collection.find_one({ "_id": parent_id })
    if parent:
        new_level = parent['level'] + 1
        absolute_parent_id = parent['absolute_parent_id']
    else:
        parent = categories_collection.find_one({ "_id": parent_id })

        if not parent:
            raise HTTPException(status_code=404, detail="New parent not found")

        new_level = 1
        absolute_parent_id = parent_id

    if parent_id == s_id:
        raise HTTPException(status_code=400, detail="Cannot move subcategory under itself")

    descendants = list(subcategories_collection.find({ "absolute_parent_id": subcategory["absolute_parent_id"] }))
    descendant_ids = {item["_id"] for item in descendants}

    current = parent

    while current and current.get("_id") in descendant_ids | {s_id}:
        if current["_id"] == s_id:
            raise HTTPException(status_code=409, detail="Cannot move a subcategory under its descendant")

        current = subcategories_collection.find_one({
            "_id": current.get("parent_id")
        })

    subcategories_collection.update_one(
        { "_id": s_id },
        {
            "$set": {
                "parent_id": parent_id,
                "absolute_parent_id": absolute_parent_id,
                "level": new_level
            }
        }
    )

    return {
        "ok": True,
        "message": "Subcategory moved successfully",
        "new_level": new_level
    }
