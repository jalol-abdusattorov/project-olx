from fastapi.security import HTTPBearer


swagger_bearer_scheme = HTTPBearer(auto_error=False)
