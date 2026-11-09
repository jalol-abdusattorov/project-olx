from pydantic import BaseModel, Field


class UserRequest(BaseModel):
    username: str
    email: str = 'user@example.com'
    password: str = Field(..., min_length=5, max_length=72)

    # Profile
    fullname: str
    phone: str
    about: str | None = None

    # Location
    country: str
    city: str
    district: str


class SubcategoryRequest(BaseModel):
    parent_id: str
    name: str
    level: int