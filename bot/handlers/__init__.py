from .user import router as user_router
from .owner import router as owner_router
from .projects import router as projects_router
from .support import router as support_router
from .broadcast import router as broadcast_router


def register_handlers() -> list:
    return [user_router, owner_router, projects_router, support_router, broadcast_router]
