from datetime import datetime as dt, timezone
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from mongodb import *
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


# AUTHORIZED & ADMIN
@router.post('/category/global')
def create_global_category(
    category_name: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    new_category = {
        "name": category_name,
        "created_at": dt.now(timezone.utc),
    }

    category_id = categories_collection.insert_one(new_category).inserted_id

    return {
        "ok": True,
        "category_id": str(category_id)
    }


# AUTHORIZED & ADMIN
@router.put('/category/global')
def rename_global_category(
    category_id: str,
    name: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    name = name.strip()

    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name can't be empty")

    try:
        c_id = ObjectId(category_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    old_category = categories_collection.find_one({ "_id": c_id })
    if not old_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    if old_category.get('name') == name:
        return {
            "ok": True,
            "category_id": category_id,
            "message": "New name is same as the old name"
        }

    categories_collection.update_one({ "_id": c_id }, { "$set": { "name": name } })

    return {
        "ok": True,
        "category_id": category_id,
        "old_name": old_category.get('name'),
        "new_name": name
    }


# AUTHORIZED & ADMIN
@router.delete('/category/global')
def delete_global_category(
    category_id: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        c_id = ObjectId(category_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    del_count = categories_collection.delete_one({ "_id": c_id }).deleted_count

    if del_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    return {
        "ok": True,
        "status": "deleted",
        "categoriy_id": category_id
    }
