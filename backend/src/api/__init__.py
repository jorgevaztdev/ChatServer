from fastapi import APIRouter
from .auth import router as auth_router
from .ws import router as ws_router
from .rooms import router as rooms_router
from .messages import router as messages_router
from .friends import router as friends_router
from .bans import router as bans_router
from .moderation import router as moderation_router
from .files import router as files_router
from .admin import router as admin_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(ws_router, tags=["websocket"])
router.include_router(rooms_router, tags=["rooms"])
router.include_router(messages_router, tags=["messages"])
router.include_router(friends_router, tags=["friends"])
router.include_router(bans_router, tags=["bans"])
router.include_router(moderation_router, tags=["moderation"])
router.include_router(files_router, tags=["files"])
router.include_router(admin_router, tags=["admin"])
