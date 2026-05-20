# 路由模块初始化
from .download import router as download_router
from .local import router as local_router
from .progress import router as progress_router

__all__ = ['download_router', 'local_router', 'progress_router']