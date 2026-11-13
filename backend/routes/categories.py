from datetime import datetime as dt, timezone
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.services.auth_service import get_current_user_id
from mongodb import *
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


def serialize(children: list):
    for child in children:
        child['_id'] = str(child['_id'])
        child['parent_id'] = str(child['parent_id'])
        child['absolute_parent_id'] = str(child['absolute_parent_id'])

    return children


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
@router.put('/category/global/{category_id}')
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
@router.delete('/category/global/{category_id}')
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


# AUTHORIZED
@router.get('/categories')
def get_all_categories(
    current_user: str = Depends(get_current_user_id)
):
    categories = list(categories_collection.find())
    if not categories:
        return {
            "ok": True,
            "message": "There are no categories available.",
            "categories": {},
        }

    categories_id = [i['_id'] for i in categories]

    #  category_id: children
    category_map = {}

    for category_id in categories_id:
        children = serialize(list(subcategories_collection.find({ "absolute_parent_id": category_id }).sort({ "level": 1 })))
        category_map[str(category_id)] = children

    return {
        "ok": True,
        "categories": category_map   
    }
