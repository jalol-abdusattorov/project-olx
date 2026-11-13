from datetime import datetime as dt, timezone
from typing import Annotated
import bson
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status
import random

from mongodb import *
from models import SubcategoryRequest
from routes.route_utils import swagger_bearer_scheme


router = APIRouter()
invalid_id_exception = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")
permission_denied_exception = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


# AUTHORIZED & ADMIN
@router.post('/subcategory')
def create_subcategory(
    subcategory: SubcategoryRequest,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        parent_category_id = ObjectId(subcategory.parent_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    name = subcategory.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Subcategory name cannot be empty")

    if subcategory.level < 1:
        raise HTTPException(
            status_code=400,
            detail="Invalid subcategory level"
        )

    # Make sure that the subcategory's parent exists
    if subcategory.level != 1:
        parent = subcategories_collection.find_one({ "_id": parent_category_id })
        if not parent:
            raise HTTPException(status_code=404, detail="Parent subcategory not found")

        if parent.get('level') != subcategory.level - 1:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid level {subcategory.level}. Expected level {parent.get('level') + 1}"
            )
        
        absolute_parent_id = parent['absolute_parent_id']

    else:
        parent = categories_collection.find_one({ "_id": parent_category_id })
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")

        absolute_parent_id = parent['_id']

    # Dont allow duplicate names, but allow, only if they are not in the same level
    subcategory_exists = subcategories_collection.find_one({ "name": name, "parent_id": parent_category_id })
    if subcategory_exists:
        raise HTTPException(status_code=409, detail=f"Subcategory '{name}' already exists")


    new_subcategory = {
        "parent_id": parent_category_id,
        "absolute_parent_id": absolute_parent_id,
        "name": name,
        "level": subcategory.level,
        "created_at": dt.now(timezone.utc)
    }

    subcategory_id = subcategories_collection.insert_one(new_subcategory).inserted_id

    return {
        "ok": True,
        "subcategory_id": str(subcategory_id),
    }


# AUTHORIZED & ADMIN
@router.put('/subcategory/rename/{subcategory_id}')
def rename_subcategory(
    subcategory_id: str,
    name: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="New name can't be empty")

    try:
        s_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    subcategory = subcategories_collection.find_one({ "_id": s_id })
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    if subcategory['name'] == name:
        return {
            "ok": True,
            "subcategory_id": subcategory_id,
            "message": "New name is same as the old name"
        }

    subcategories_collection.update_one({ "_id": s_id }, { "$set": { "name": name } })

    return {
        "ok": True,
        "subcategory_id": subcategory_id,
        "old_name": subcategory['name'],
        "new_name": name
    }


# AUTHORIZED & ADMIN
@router.put("/subcategory/move/{subcategory_id}")
def move_subcategory(
    subcategory_id: str,
    new_parent_id: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    # Get the subcategory being moved
    subcategory = subcategories_collection.find_one({
        "_id": ObjectId(subcategory_id)
    })

    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    # Get the new parent
    new_parent = categories_collection.find_one({
        "_id": ObjectId(new_parent_id)
    }) or subcategories_collection.find_one({
        "_id": ObjectId(new_parent_id)
    })

    if not new_parent:
        raise HTTPException(status_code=404, detail="New parent not found")

    old_level = subcategory["level"]
    old_absolute_parent_id = subcategory["absolute_parent_id"]

    # Determine the new level and global category
    if "level" in new_parent:
        new_level = new_parent["level"] + 1
        new_absolute_parent_id = new_parent["absolute_parent_id"]
    else:
        new_level = 1
        new_absolute_parent_id = new_parent["_id"]

    # Prevent moving into itself
    if str(subcategory["_id"]) == str(new_parent["_id"]):
        raise HTTPException(status_code=400, detail="Cannot move a subcategory into itself")

    # Find all descendants
    descendant_ids = set()
    queue = [subcategory["_id"]]

    while queue:
        current_id = queue.pop(0)

        children = list(subcategories_collection.find(
            {"parent_id": current_id},
            {"_id": 1}
        ))

        for child in children:
            if child["_id"] not in descendant_ids:
                descendant_ids.add(child["_id"])
                queue.append(child["_id"])

    # Prevent circular hierarchy
    if new_parent["_id"] in descendant_ids:
        raise HTTPException(status_code=400, detail="Cannot move a subcategory into its own descendant")

    # Check whether the global category is changing
    different_global_category = (
        old_absolute_parent_id != new_absolute_parent_id
    )

    if different_global_category:

        # Scenario 1: Moving a level 1 subcategory to another global category
        if old_level == 1:

            direct_children = list(subcategories_collection.find({
                "parent_id": subcategory["_id"]
            }))

            if direct_children:
                # Randomly promote one direct child
                promoted_child = random.choice(direct_children)
                promoted_child_id = promoted_child["_id"]

                # Find descendants of the promoted child
                promoted_descendant_ids = set()
                queue = [promoted_child_id]

                while queue:
                    current_id = queue.pop(0)

                    children = list(subcategories_collection.find(
                        {"parent_id": current_id},
                        {"_id": 1}
                    ))

                    for child in children:
                        if child["_id"] not in promoted_descendant_ids:
                            promoted_descendant_ids.add(child["_id"])
                            queue.append(child["_id"])

                # Promote the selected child to level 1
                subcategories_collection.update_one(
                    {"_id": promoted_child_id},
                    {"$set": {
                        "parent_id": old_absolute_parent_id,
                        "absolute_parent_id": old_absolute_parent_id,
                        "level": 1
                    }}
                )

                # Shift the promoted child's descendants up one level
                if promoted_descendant_ids:
                    subcategories_collection.update_many(
                        {"_id": {"$in": list(promoted_descendant_ids)}},
                        {
                            "$inc": {"level": -1},
                            "$set": {
                                "absolute_parent_id": old_absolute_parent_id
                            }
                        }
                    )

                # Reassign remaining direct children under the promoted child
                remaining_children = [
                    child["_id"]
                    for child in direct_children
                    if child["_id"] != promoted_child_id
                ]

                if remaining_children:
                    subcategories_collection.update_many(
                        {"_id": {"$in": remaining_children}},
                        {"$set": {
                            "parent_id": promoted_child_id
                        }}
                    )

            # All descendants stay in the original global category
            moving_descendant_ids = set()

        # Scenario 2: Moving a level 2+ subcategory to another global category
        else:
            moving_descendant_ids = descendant_ids

            # Shift the entire subtree by the same level difference
            level_difference = new_level - old_level

            if moving_descendant_ids and level_difference != 0:
                subcategories_collection.update_many(
                    {"_id": {"$in": list(moving_descendant_ids)}},
                    {"$inc": {"level": level_difference}}
                )

        # Update the global category of descendants that follow the moved node
        if moving_descendant_ids:
            subcategories_collection.update_many(
                {"_id": {"$in": list(moving_descendant_ids)}},
                {"$set": {
                    "absolute_parent_id": new_absolute_parent_id
                }}
            )

    # Scenario 3 and 4: Moving within the same global category
    else:
        moving_descendant_ids = descendant_ids

        level_difference = new_level - old_level

        if moving_descendant_ids and level_difference != 0:
            subcategories_collection.update_many(
                {"_id": {"$in": list(moving_descendant_ids)}},
                {"$inc": {"level": level_difference}}
            )

    # Finally, update the moved subcategory itself
    subcategories_collection.update_one(
        {"_id": subcategory["_id"]},
        {"$set": {
            "parent_id": new_parent["_id"],
            "absolute_parent_id": new_absolute_parent_id,
            "level": new_level
        }}
    )

    return {
        "ok": True,
        "message": "Subcategory moved successfully",
        "new_level": new_level,
        "global_category_changed": different_global_category
    }


# AUTHORIZED & ADMIN
@router.delete('/subcategory/{subcategory_id}')
def delete_subcategory(
    subcategory_id: str,
    request: Request,
    _: Annotated[str, Depends(swagger_bearer_scheme)]
):
    if not request.state.admin:
        raise permission_denied_exception

    try:
        s_id = ObjectId(subcategory_id)
    except bson.errors.InvalidId:
        raise invalid_id_exception

    subcategory = subcategories_collection.find_one({ "_id": s_id })
    if not subcategory:
        raise HTTPException(status_code=404, detail="Subcategory not found")


    del_count = subcategories_collection.delete_one({ "_id": s_id })

    # Delete the subcategories behind this subcategory
    deleted_decendants_count = subcategories_collection.delete_many({ "absolute_parent_id": subcategory['absolute_parent_id'], "level": { "$gt": subcategory['level'] } }).deleted_count

    subcategory['_id'] = str(subcategory['_id'])
    subcategory['parent_id'] = str(subcategory['parent_id'])
    subcategory['absolute_parent_id'] = str(subcategory['absolute_parent_id'])

    return {
        "ok": True,
        "subcategory_id": subcategory_id,
        "deleted": f"{"Success" if del_count != 0 else "Failure"}",
        "children_deleted": deleted_decendants_count,
        "subcategory": subcategory
    }
