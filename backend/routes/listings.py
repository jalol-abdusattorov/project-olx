from datetime import datetime as dt, timezone, timedelta
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from models import ListingRequest
from mongodb import *
from auth.services.auth_service import get_current_user_id
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")


# AUTHORIZED
@router.post("/listing")
def create_listing(
    listing: ListingRequest,
    attributes: dict,
    current_user: str = Depends(get_current_user_id),
):
    title = listing.title.strip()
    if not title: raise HTTPException(status_code=400, detail="Title can't be empty")

    description = listing.description.strip()
    if not description: raise HTTPException(status_code=400, detail="Description can't be empty")

    current_subcategory = listing.subcategory_path[-1]
    print(current_subcategory)

    expiration = dt.now(timezone.utc) + timedelta(days=listing.expires_in)

    new_listing = {
        "seller_id": ObjectId(current_user),
        "title": title,
        "description": description,

        "category": listing.category_id,
        "subcategory_path": listing.subcategory_path,
        "current_subcategory": current_subcategory,

        "location": {
            "country": listing.location.country,
            "city": listing.location.city,
            "district": listing.location.district
        },
        "attributes": attributes,

        "status": "active", # --  "sold" / "expired"
        "views_count": 0,
 
        "created_at": dt.now(timezone.utc),
        "expires_at": expiration
    }

    listing_id = listings_collection.insert_one(new_listing).inserted_id

    return {
        "ok": True,
        "_id": str(listing_id),
        "expiration": expiration
    }

