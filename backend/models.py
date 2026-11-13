from typing import Literal
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


    @model_validator(mode="after")
    def validate_empty_values(self):
        self.city = self.city.strip()
        self.district = self.district.strip()

        if not self.city or not self.district:
            raise ValueError("Values cannot be empty")

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
        try:
            self.category_id = ObjectId(self.category_id)
            self.subcategory_path = list({ObjectId(i) for i in self.subcategory_path})
        except bson.errors.InvalidId:
            raise ValueError(f"Invalid ID format")

        category = categories_collection.find_one({ "_id": self.category_id })
        if not category:
            raise ValueError(f"Category not found")

        subcategories = list(subcategories_collection.find({ "_id": { "$in": self.subcategory_path }, "absolute_parent_id": self.category_id }, { "name": 1, "level": 1, "parent_id": 1 }).sort({ "level": 1 }))
        if len(subcategories) != len(self.subcategory_path):
            raise ValueError(f"Invalid subcategories")

        return self



