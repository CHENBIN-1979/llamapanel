#!/usr/bin/env python3
import time
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path
from . import get_model_manager

router = APIRouter(prefix="/api/local", tags=["local"])

# 读取 HTML 文件
def read_html_file(filename):
    filepath = Path(__file__).parent.parent / "templates" / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>页面加载失败</h1>"

LOCAL_HTML = read_html_file("local.html")

@router.get("/page", response_class=HTMLResponse)
async def local_page():
    """本地模型页面"""
    return HTMLResponse(content=LOCAL_HTML)

@router.get("/list")
async def get_local_models():
    """获取本地已下载的模型列表"""
    mm = get_model_manager()
    models = mm.get_local_models()
    
    # 添加部分下载的文件
    partial_files = []
    for item in mm.models_dir.rglob('*.partial'):
        if item.is_file():
            size = item.stat().st_size
            size_gb = size / (1024 * 1024 * 1024)
            rel_path = item.relative_to(mm.models_dir)
            partial_files.append({
                'name': str(rel_path),
                'path': str(item),
                'size': size,
                'size_str': f"{size_gb:.2f} GB",
                'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.stat().st_mtime)),
                'is_partial': True
            })
    
    models.extend(partial_files)
    return {"success": True, "models": sorted(models, key=lambda x: x['name'])}

@router.delete("/delete")
async def delete_model(filename: str):
    """删除本地模型"""
    mm = get_model_manager()
    success = mm.delete_model(filename)
    if success:
        return {"success": True, "message": f"已删除 {filename}"}
    else:
        return {"success": False, "message": "删除失败"}

@router.post("/symlinks")
async def create_symlinks():
    """创建所有模型的软链接"""
    mm = get_model_manager()
    count = mm.create_symlinks()
    return {"success": True, "message": f"已创建 {count} 个软链接"}