from typing import Any, Literal
from bson import ObjectId
import bson
from pydantic import BaseModel, Field, model_validator
from pydantic_extra_types.country import CountryAlpha3
from mongodb import *
import geonamescache


class UserRequest(BaseModel):
    username: str
    email: str = 'user@example.com'
    password: str = Field(..., min_length=5, max_length=72)

    # Profile
    fullname: str
    phone: str
    about: str | None = None

    location: Location


class SubcategoryRequest(BaseModel):
    parent_id: str
    name: str
    level: int


gc = geonamescache.GeonamesCache()
CITIES_DB = gc.get_cities()

class Location(BaseModel):
    country: CountryAlpha3
    city: str
    district: str


    @model_validator(mode="after")
    def validate_city_belongs_to_country(self) -> "Location":
        self.city = self.city.strip()
        self.district = self.district.strip()

        if not self.city or not self.district:
            raise ValueError("Values cannot be empty")
        
        city_lower = self.city.lower()
        country_code = self.country.alpha2.upper()

        # Check if any record matches both the city name and the country code
        match_found = any(
            c["name"].lower() == city_lower and c["countrycode"] == country_code
            for c in CITIES_DB.values()
        )

        if not match_found:
            raise ValueError(f"The city '{self.city}' was not found in country code '{self.country}'.")
        
        return self


class ListingRequest(BaseModel):
    title: str
    description: str
    category_id: str

    # [ "6ab2...", "6ab45..." ]
    subcategory_path: list
    location: Location
    expires_in: int = 30 # days

    @model_validator(mode="after")
    def validate_ids(self):
        """
        Validates ids, insures subcategory_path is correct, and in the right hierarchy order.
        hierarchy: 
        [level_1, level_2, level_3, ...] / Parent -> child / Ascending order
        """

        try:
            self.category_id = ObjectId(self.category_id)

            seen = set()
            unique_sub_path = []
            for subcategory_id in self.subcategory_path:
                sub_id = ObjectId(subcategory_id)

                if sub_id not in seen:
                    seen.add(sub_id)
                    unique_sub_path.append(sub_id)

            self.subcategory_path = unique_sub_path

        except bson.errors.InvalidId:
            raise ValueError(f"Invalid ID format")

        category = categories_collection.find_one({ "_id": self.category_id })
        if not category:
            raise ValueError(f"Category not found")

        subcategories = list(subcategories_collection.find(
            {
                "_id": { "$in": self.subcategory_path },
                "absolute_parent_id": self.category_id
            },
        ).sort({ "level": 1 }))

        if len(subcategories) != len(self.subcategory_path):
            raise ValueError(f"One or more subcategories doesn't exist or doesn't belong in the same category.")

        sub_map = {sub['_id']: sub for sub in subcategories}
        for i, sub_id in enumerate(self.subcategory_path):
            current = sub_map[sub_id]

            if i == 0:
                if current.get('parent_id') != self.category_id:
                    raise ValueError("First subcategory must be direct child of main category")
            else:
                prev_id = self.subcategory_path[i - 1]
                if current.get('parent_id') !=  prev_id:
                    raise ValueError("Subcategories are in the wrong hierarchy order")

        return self


class AttributeRequest(BaseModel):
    category_id: str
    subcategory_id: str
    attributes: dict[str, Any]

    @model_validator(mode="after")
    def validate_ids(self):
        try:
            self.category_id = ObjectId(self.category_id)
            self.subcategory_id = ObjectId(self.subcategory_id)
        except bson.errors.InvalidId:
            raise ValueError(f"Invalid ID format")

        category = categories_collection.find_one({ "_id": self.category_id })
        subcategory = subcategories_collection.find_one({ "_id": self.subcategory_id })

        if not category: raise ValueError(f"Category not found")
        if not subcategory: raise ValueError(f"Subcategory not found")

        attr = attributes_collection.find_one({ "category_id": self.category_id, "subcategory_id": self.subcategory_id })
        if attr:
            raise ValueError("Attribute already exists")

        return self
