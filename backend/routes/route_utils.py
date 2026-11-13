import bson
from bson import ObjectId
from fastapi.security import HTTPBearer

from models import ListingRequest


swagger_bearer_scheme = HTTPBearer(auto_error=False)
