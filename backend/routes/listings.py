from datetime import datetime as dt, timezone, timedelta
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from models import ListingRequest
from mongodb import *
from auth.services.auth_service import get_current_user_id
from routes.route_utils import belongs_to_attribute, serialize_listings, swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")


# AUTHORIZED
@router.post("/listings")
def create_listing(
    listing: ListingRequest,
    attribute_id: str,
    attributes: dict,
    current_user: str = Depends(get_current_user_id),
):
    try:attribute_id = ObjectId(attribute_id)
    except bson.errors.InvalidId: raise invalid_id_exception

    title = listing.title.strip()
    if not title: raise HTTPException(status_code=400, detail="Title can't be empty")

    description = listing.description.strip()
    if not description: raise HTTPException(status_code=400, detail="Description can't be empty")

    if not belongs_to_attribute(attribute_id, attributes):
        raise HTTPException(status_code=403, detail="Attribute doesn't match")

    current_subcategory = listing.subcategory_path[-1]

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
        # "attribute_id": str(attribute_id),
        "attributes": attributes,
        "payment": {
            "payment_method": listing.payment.payment_method,
            "price": listing.payment.price,
            "currency": listing.payment.currency,
        },

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


# AUTHORIZED
@router.get("/listings")
def get_listings(
    subcategory_id: str,
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: str = Depends(get_current_user_id)
):
    try:
        sub_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    query = {
        "current_subcategory": sub_id,
        "status": "active",
        "expires_at": { "$gt": dt.now(timezone.utc) }
    }

    projection = {
        "seller_id": 1,
        "title": 1,
        "description": 1,

        "category": 1,
        "subcategory_path": 1,
        "current_subcategory": 1,

        "location": 1,
        "attributes": 1,

        "views_count": 1,
        "created_at": 1,
    }

    cursor = (
        listings_collection.find(query, projection)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    listings = list(cursor)

    return {
        "ok": True,
        "count": len(listings),
        "listings": serialize_listings(listings),
    }


# AUTHORIZED
@router.delete("/listings/{listing_id}")
def delete_listing(
    listing_id: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)],
):
    try:
        listing_id = ObjectId(listing_id)
        user_id = ObjectId(request.state.user['sub'])
    except bson.errors.InvalidId:
        raise invalid_id_exception

    listing = listings_collection.find_one({ "_id": listing_id })
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("seller_id") != user_id:
        raise HTTPException(status_code=403, detail="Can't delete others listing")

    del_count = listings_collection.delete_one({ "_id": listing_id }).deleted_count

    return {
        "ok": True,
        "listing_id": str(listing_id),
        "deleted": "Success" if del_count else "Failed",
    }

