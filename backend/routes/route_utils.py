from bson import ObjectId
from fastapi import HTTPException
from fastapi.security import HTTPBearer

from models import ListingRequest
from mongodb import attributes_collection


swagger_bearer_scheme = HTTPBearer(auto_error=False)

def serialize_listings(listings: list):
    for listing in listings:
        listing['_id'] = str(listing['_id'])
        listing['seller_id'] = str(listing['seller_id'])
        listing['category'] = str(listing['category'])
        listing['current_subcategory'] = str(listing['current_subcategory'])

        if 'subcategory_path' in listing:
            listing['subcategory_path'] = [str(i) for i in listing['subcategory_path']]

    return listings


def belongs_to_attribute(attribute_id: ObjectId, attributes: dict) -> bool: 
    attr = attributes_collection.find_one({ "_id": attribute_id })
    if not attr:
        raise HTTPException(status_code=404, detail="Attribute not found")

    if attr['attributes'].keys() != attributes.keys():
        return False

    for instance, attribute_value in zip(attr['attributes'].values(), attributes.values()):
        attr_instance = str(type(attribute_value))[8:-2]

        if attr_instance != instance:
            raise HTTPException(status_code=403, detail=f"Expected instance {instance}, got {attr_instance}")

    return True