from .bell import router as bell_router
from .privacy import router as privacy_router
from .schedule import router as schedule_router
from .start import router as start_router
from .teacher_schedule import router as teacher_router

__all__ = [
    "bell_router",
    "privacy_router",
    "schedule_router",
    "start_router",
    "teacher_router",
]
