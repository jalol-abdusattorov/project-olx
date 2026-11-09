from datetime import datetime as dt, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status

from models import UserRequest
from mongodb import *
from auth.utils.auth_utils import get_password_hash
from routes.route_utils import swagger_bearer_scheme
from auth.services.auth_service import create_acces_token

router = APIRouter()



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
            'country': user.country,
            'city': user.city,
            'district': user.district,
        },
        'role': 'user',
        'created_at': dt.now(timezone.utc)
    }

    user_id = users_collection.insert_one(new_user).inserted_id

    
    access_token_expires = timedelta(minutes=1440)
    access_token = create_acces_token(
        data={'sub': user.email, 'admin': False, 'uid': str(user_id)},
        expires_delta=access_token_expires
    )

    return {"user-id": str(user_id), "token": access_token}
    # return {"private": "property"}

