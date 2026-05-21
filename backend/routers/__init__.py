# 路由模块初始化
from .download import router as download_router
from .local import router as local_router
from .progress import router as progress_router

# 全局 ModelManager 实例
_model_manager = None

def set_model_manager(mm):
    global _model_manager
    _model_manager = mm

def get_model_manager():
    return _model_manager

__all__ = ['download_router', 'local_router', 'progress_router', 'set_model_manager', 'get_model_manager']