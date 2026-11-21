import os
from dotenv import load_dotenv, find_dotenv
from contextlib import asynccontextmanager
from datetime import datetime as dt, timezone
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import jwt

from mongodb import listings_collection
from routes.users import router as users_router
from auth.routes.auth_router import auth_router
from routes.categories import router as categories_router
from routes.subcategories import router as subcategories_router
from routes.listings import router as listings_router
from routes.attributes import router as attributes_router
from routes.filters import router as filters_router


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
            request.state.admin = payload.get('admin', False)

        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=403, content={"detail": "Token has expired"})
        except jwt.PyJWTError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)


def update_expired_listings():
    """Runs periodically in the background to bulk-update expired listings."""
    result = listings_collection.update_many(
        {
            "expires_at": { "$lt": dt.now(timezone.utc) },
            "status": { "$ne": "expired" }
        },
        {
            "$set": {
                "status": "expired"
            }
        }
    )

    if result.modified_count > 0:
        print(f"Background task: Expired {result.modified_count} listings.")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    scheduler.add_job(update_expired_listings, "interval", minutes=3)
    scheduler.start()
    print("Scheduler started.")
    
    yield

    # --- SHUTDOWN ---
    scheduler.shutdown()
    print("Scheduler shut down.")


app = FastAPI(title="Olx", lifespan=lifespan)
app.add_middleware(AuthMiddleware)

app.include_router(users_router, tags=['Users'])
app.include_router(auth_router, prefix='/api')
app.include_router(categories_router, tags=["Categories"])
app.include_router(subcategories_router, tags=["Subcategories"])
app.include_router(listings_router, tags=["Listings"])
app.include_router(attributes_router, tags=["Attributes"])
app.include_router(filters_router, tags=["Filters"])


@app.get("/")
def get():
    return {"message": "homepage"}