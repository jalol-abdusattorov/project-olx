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
        raise invalid_id_exception



# AUTHORIZED
@router.get("/attributes/{subcategory_id}")
def get_subcategory_attributes(
    subcategory_id: str,
    current_user: str = Depends(get_current_user_id)
):
    try:
        subcategory_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    pass
