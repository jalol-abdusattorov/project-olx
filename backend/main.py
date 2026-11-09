import os
from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

from routes.users import router as users_router
from auth.routes.auth_router import auth_router
from routes.categories import router as categories_router
from routes.subcategories import router as subcategories_router


dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
public_endpoints = ["/docs", "/openapi.json", "/api/auth/login", "/users", "/"]


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Open the public endpoints because they dont need auth
        if request.url.path in public_endpoints:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Not Authorized"})

        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

            # Inject user, token payload and admin status into state for auth 
            request.state.user = payload
            request.state.token_string = token
            request.state.admin = payload['admin']

        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=403, content={"detail": "Token has expired"})
        except jwt.PyJWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        except KeyError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)


app = FastAPI(title="Olx")
app.add_middleware(AuthMiddleware)

app.include_router(users_router, tags=['Users'])
app.include_router(auth_router, prefix='/api')
app.include_router(categories_router, tags=["Categories"])
app.include_router(subcategories_router, tags=["Subcategories"])


@app.get("/")
def get():
    return {"message": "homepage"}