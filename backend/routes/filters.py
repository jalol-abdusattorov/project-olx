from datetime import datetime as dt, timezone, timedelta
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from models import FilterRequest, SpecialFilterRequest
from mongodb import *
from auth.services.auth_service import get_current_user_id
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


# AUTHORIZED & ADMIN
@router.post("/filters/global")
def create_global_filter(
    global_filter: FilterRequest,

    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    if not request.state.admin:
        raise permission_denied_exception

    new_filter = global_filter.model_dump(exclude_none=True)
    new_filter['scope'] = 'global'

    filter_id = filters_collection.insert_one(new_filter).inserted_id

    return {
        "ok": True,
        "filter_id": str(filter_id)
    }


# AUTHORIZED & ADMIN
@router.post("/filters/special")
def create_special_filter(
    special_filter: SpecialFilterRequest,

    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    try:
        subcategory_id = ObjectId(special_filter.subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    if not request.state.admin:    
        raise permission_denied_exception

    new_filter = {
        "key": special_filter.key,
        "label": special_filter.label,

        "type": special_filter.type,
        "subcategory_id": subcategory_id,

        "scope": "special",
        "options": special_filter.options,

        "unit": special_filter.unit,
        "min": special_filter.min,
        "max": special_filter.max,

        "is_active": True
    }

    filter_id = filters_collection.insert_one(new_filter).inserted_id

    return {
        "ok": True,
        "filter_id": str(filter_id)
    }


# AUTHORIZED
@router.get("/filters")
def get_filters(
    active_only: bool,
    subcategory_id: str | None = None,
    current_user: str = Depends(get_current_user_id)
):
    try:
        subcategory_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    if active_only:
        global_query = {
            "scope": "global",
            "is_active": True
        }
        special_query = {
            "scope": "special",
            "subcategory_id": subcategory_id,
            "is_active": True
        }
    else:
        global_query = {
            "scope": "global",
        }
        special_query = {
            "scope": "special",
            "subcategory_id": subcategory_id,
        }

    global_filters = list(filters_collection.find(global_query))
    special_filters = list(filters_collection.find(special_query))

    for i in global_filters:
        i['_id'] = str(i['_id'])

    for j in special_filters:
        j['_id'] = str(j['_id'])
        j['subcategory_id'] = str(j['subcategory_id'])

    return {
        "ok": True,
        "global_filters": global_filters,
        "special_filters": special_filters
    }


# AUTHORIZED & ADMIN
@router.put("/filters/enable")
def enable_filter(
    filter_id: str,
    
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    try:
        filter_id = ObjectId(filter_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    if not request.state.admin:    
        raise permission_denied_exception

    update =filters_collection.update_one({ "_id": filter_id }, { "$set": { "is_active": True } })
    if update.matched_count == 0:
        raise HTTPException(status_code=404, detail="Filter not found")

    return {
        "ok": True,
        "message": "Enabling successfuly" if update.modified_count == 1 else "Already enabled, or something went wrong"
    }


# AUTHORIZED & ADMIN
@router.put("/filters/disable")
def disable_filter(
    filter_id: str,
    
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    if not request.state.admin:    
        raise permission_denied_exception

    try:
        filter_id = ObjectId(filter_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    update = filters_collection.update_one({ "_id": filter_id }, { "$set": { "is_active": False } })
    if update.matched_count == 0:
        raise HTTPException(status_code=404, detail="Filter not found")

    return {
        "ok": True,
        "message": "Disabled successfuly" if update.modified_count == 1 else "Already disabled, or something went wrong"
    }


# AUTHORIZED & ADMIN
@router.delete("/filters/{filter_id}")
def delete_filter(
    filter_id: str,

    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    if not request.state.admin:    
        raise permission_denied_exception

    try:
        filter_id = ObjectId(filter_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    deleted_count = filters_collection.delete_one({ "_id": filter_id }).deleted_count
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Filter not found")

    return {
        "ok": True,
        "message": "Deleted Successfuly" if deleted_count == 1 else f"Something went wrong, deleted {deleted_count} documents/filters"
    }
