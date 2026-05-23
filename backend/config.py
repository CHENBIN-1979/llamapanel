#!/usr/bin/env python3
"""
LlamaPanel 统一路径配置
所有数据路径集中管理，与项目代码分离。
删除/更新 llamapanel 项目不会影响模型、llama.cpp 和日志。
"""
import os
from pathlib import Path

# ==================== 项目代码路径 ====================
# llamapanel 项目根目录（代码、模板、路由等）
PROJECT_DIR = Path(__file__).resolve().parent.parent  # backend/ -> llamapanel/

# ==================== 数据存储路径 ====================
# 可通过环境变量 LLAMAPANEL_DATA_DIR 覆盖默认路径
_DATA_DIR_ENV = os.environ.get("LLAMAPANEL_DATA_DIR", "")
if _DATA_DIR_ENV:
    DATA_DIR = Path(_DATA_DIR_ENV)
else:
    # 默认：项目同级目录 /data/llamapanel
    DATA_DIR = Path("/data/llamapanel")

# 各数据子目录
MODELS_DIR = DATA_DIR / "models"          # 模型文件下载存储
LINKS_DIR = DATA_DIR / "model_links"      # 软链接目录
LOGS_DIR = DATA_DIR / "logs"              # 日志目录
LLAMA_DIR = DATA_DIR / "llama.cpp"        # llama.cpp 源码与编译产物
BUILD_DIR = LLAMA_DIR / "build"           # llama.cpp 编译输出

# ==================== 工具方法 ====================
def ensure_dirs():
    """确保所有数据目录存在"""
    for d in [DATA_DIR, MODELS_DIR, LINKS_DIR, LOGS_DIR, LLAMA_DIR, BUILD_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def get_path_info() -> dict:
    """返回所有路径的详细信息（用于系统信息页面）"""
    return {
        "project_dir": {
            "path": str(PROJECT_DIR),
            "description": "LlamaPanel 项目代码目录",
            "exists": PROJECT_DIR.exists(),
        },
        "data_dir": {
            "path": str(DATA_DIR),
            "description": "数据存储根目录（可配置环境变量 LLAMAPANEL_DATA_DIR）",
            "exists": DATA_DIR.exists(),
        },
        "models_dir": {
            "path": str(MODELS_DIR),
            "description": "模型文件下载存储",
            "exists": MODELS_DIR.exists(),
        },
        "links_dir": {
            "path": str(LINKS_DIR),
            "description": "模型软链接目录（llama.cpp 使用此路径加载模型）",
            "exists": LINKS_DIR.exists(),
        },
        "logs_dir": {
            "path": str(LOGS_DIR),
            "description": "运行日志目录",
            "exists": LOGS_DIR.exists(),
        },
        "llama_dir": {
            "path": str(LLAMA_DIR),
            "description": "llama.cpp 源码目录",
            "exists": LLAMA_DIR.exists(),
        },
        "build_dir": {
            "path": str(BUILD_DIR),
            "description": "llama.cpp 编译产物目录",
            "exists": BUILD_DIR.exists(),
        },
    }
