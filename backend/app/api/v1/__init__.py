from fastapi import APIRouter

from app.api.v1 import auth, chat, classification, documents, search, system

api_router = APIRouter()
for module in (auth, documents, search, chat, classification, system):
    api_router.include_router(module.router)
