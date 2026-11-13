from datetime import datetime as dt, timedelta, timezone
from typing import Annotated
from bson import ObjectId
import bson
from fastapi import APIRouter, Depends, HTTPException, Request, status

from auth.models.token import Token
from models import UserRequest
from mongodb import *
from auth.utils.auth_utils import get_password_hash
from routes.route_utils import swagger_bearer_scheme
from auth.services.auth_service import create_access_token, get_current_user_id


router = APIRouter()

invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
# permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@router.post("/users")
def create_user(
    user: UserRequest
):
    if len(user.password) > 72: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="password length should be less than 72 characters")

    is_unique_email = users_collection.find_one({ 'email': user.email })
    if is_unique_email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is used")


    new_user = {
        'username': user.username,
        'email': user.email,
        'password_hash': get_password_hash(user.password),

        'profile': {
            'fullname': user.fullname,
            'phone': user.phone,
            'about': user.about,
        },

        'location': {
            'country': user.location.country,
            'city': user.location.city,
            'district': user.location.district,
        },
        'role': 'user',
        'created_at': dt.now(timezone.utc)
    }

    user_id = users_collection.insert_one(new_user).inserted_id

    
    access_token_expires = timedelta(minutes=1440)
    access_token = create_access_token(
        data={'sub': str(user_id), 'email': new_user['email']},
        expires_delta=access_token_expires
    )

    return {"user-id": str(user_id), "token": Token(access_token=access_token, token_type='bearer')}


# AUTHORIZED
@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    current_user: str = Depends(get_current_user_id),
):
    try:
        uid = ObjectId(user_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    user = users_collection.find_one({  "_id": uid })
    del user['password_hash']
    del user['email']
    del user['_id']

    return {
        "ok": True,
        "user": user,
    }
