#!/usr/bin/env python3
import time
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates
from pathlib import Path
import jinja2
from model_manager import ModelManager

router = APIRouter(prefix="/api/local", tags=["local"])
model_manager = ModelManager()

# 设置模板目录 - 使用 jinja2.Environment 禁用缓存
templates_dir = Path(__file__).parent.parent / "templates"
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(templates_dir)),
    enable_async=True,
    cache_size=0
)
templates = Jinja2Templates(env=env)

@router.get("/page", response_class=HTMLResponse)
async def local_page(request: Request):
    """本地模型页面"""
    return templates.TemplateResponse("local.html", {"request": request, "active_page": "local"})

@router.get("/list")
async def get_local_models():
    """获取本地已下载的模型列表"""
    models = model_manager.get_local_models()
    
    # 添加部分下载的文件
    partial_files = []
    for item in model_manager.models_dir.rglob('*.partial'):
        if item.is_file():
            size = item.stat().st_size
            size_gb = size / (1024 * 1024 * 1024)
            rel_path = item.relative_to(model_manager.models_dir)
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
    success = model_manager.delete_model(filename)
    if success:
        return {"success": True, "message": f"已删除 {filename}"}
    else:
        return {"success": False, "message": "删除失败"}

@router.post("/symlinks")
async def create_symlinks():
    """创建所有模型的软链接"""
    count = model_manager.create_symlinks()
    return {"success": True, "message": f"已创建 {count} 个软链接"}