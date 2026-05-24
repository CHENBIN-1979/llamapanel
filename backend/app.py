#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
import subprocess
import os
import time
import threading

# 动态获取 backend 目录路径，支持本地开发和服务器部署
sys.path.append(str(Path(__file__).parent))
from installer import LlamaCppInstaller
from routers import download_router, local_router, progress_router, system_router, server_router, set_model_manager
from model_manager import ModelManager
from config import PROJECT_DIR, LOGS_DIR, ensure_dirs

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

# 创建全局单例 ModelManager 并设置到路由模块
model_manager = ModelManager()
set_model_manager(model_manager)

# 注册路由
app.include_router(download_router)
app.include_router(local_router)
app.include_router(progress_router)
app.include_router(system_router)
app.include_router(server_router)

# ==================== LlamaPanel 更新状态跟踪 ====================
_update_panel_status = {
    "running": False,
    "success": None,
    "message": "",
    "started_at": None,
    "finished_at": None,
}
_update_panel_lock = threading.Lock()

# ... (rest of app.py content follows the same pattern as original)