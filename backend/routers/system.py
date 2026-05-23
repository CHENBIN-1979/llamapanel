#!/usr/bin/env python3
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

router = APIRouter(prefix="/api/system", tags=["system"])

def read_html_file(filename):
    filepath = Path(__file__).parent.parent / "templates" / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>页面加载失败</h1>"

SYSTEM_HTML = read_html_file("system.html")

@router.get("/page", response_class=HTMLResponse)
async def system_page():
    """系统信息页面"""
    return HTMLResponse(content=SYSTEM_HTML)

@router.get("/paths")
async def get_paths_info():
    """获取所有路径信息"""
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from config import get_path_info, PROJECT_DIR, DATA_DIR, MODELS_DIR, LINKS_DIR, LOGS_DIR, LLAMA_DIR
    from installer import LlamaCppInstaller
    
    installer = LlamaCppInstaller()
    status = installer.get_status()
    
    # 计算目录大小
    def get_dir_size(path):
        total = 0
        try:
            for entry in path.rglob('*'):
                if entry.is_file():
                    total += entry.stat().st_size
        except:
            pass
        return total
    
    def format_size(size):
        if size == 0:
            return "空"
        size_gb = size / (1024 * 1024 * 1024)
        if size_gb >= 1:
            return f"{size_gb:.2f} GB"
        size_mb = size / (1024 * 1024)
        if size_mb >= 1:
            return f"{size_mb:.2f} MB"
        return f"{size / 1024:.1f} KB"
    
    paths = get_path_info()
    
    # 添加磁盘使用情况
    import shutil as sh
    disk_usage = sh.disk_usage(str(DATA_DIR)) if DATA_DIR.exists() else None
    
    return {
        "paths": paths,
        "llama_status": {
            "cloned": status.get("cloned", False),
            "built": status.get("built", False),
            "version": status.get("version", "未知"),
            "server_path": status.get("server_path"),
            "has_update": status.get("has_update", False),
            "latest_version": status.get("latest_version"),
        },
        "disk_usage": {
            "total": format_size(disk_usage.total) if disk_usage else "未知",
            "used": format_size(disk_usage.used) if disk_usage else "未知",
            "free": format_size(disk_usage.free) if disk_usage else "未知",
        },
        "dir_sizes": {
            "models": format_size(get_dir_size(MODELS_DIR)) if MODELS_DIR.exists() else "空",
            "links": format_size(get_dir_size(LINKS_DIR)) if LINKS_DIR.exists() else "空",
            "llama": format_size(get_dir_size(LLAMA_DIR)) if LLAMA_DIR.exists() else "空",
        }
    }
