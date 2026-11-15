from datetime import datetime as dt, timezone, timedelta
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from models import AttributeRequest
from mongodb import *
from auth.services.auth_service import get_current_user_id
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


# AUTHORIZED & ADMIN
@router.post("/attributes")
def create_attribute(
    attribute: AttributeRequest,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    new_attributes = {
        "category_id": attribute.category_id,
        "subcategory_id": attribute.subcategory_id,
        "attributes": attribute.attributes
    }

    attr_id = attributes_collection.insert_one(new_attributes).inserted_id

    return {
        "ok": True,
        "attr_id": str(attr_id)
    }


# AUTHORIZED
@router.get("/attributes")
def get_subcategory_attributes(
    subcategory_id: str | None = None,
    attribute_id: str | None = None, 
    current_user: str = Depends(get_current_user_id)
):
    if not subcategory_id and not attribute_id:
        return HTTPException(status_code=400, detail="Client didn't send required data")

    try:
        subcategory_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    if not attribute_id:
        attr = attributes_collection.find_one({ "subcategory_id": subcategory_id })
    else:
        attr = attributes_collection.find_one({ "_id": attribute_id })

    attr['_id'] = str(attr['_id'])
    attr['category_id'] = str(attr['category_id'])
    attr['subcategory_id'] = str(attr['subcategory_id'])

    return {
        "ok": True,
        "attribute": attr if attr else "Attribute doesn't exist"
    }


# AUTHORIZED & ADMIN
@router.delete("/attributes")
def delete_attribute(
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],

    subcategory_id: str,
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        subcategory_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    del_count = attributes_collection.delete_one({ "subcategory_id": subcategory_id }).deleted_count

    return {
        "ok": True,
        "message": "Deleted successfuly" if del_count == 1 else "Something went wrong"
    }
