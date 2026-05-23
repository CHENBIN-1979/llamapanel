#!/usr/bin/env python3
import os
import time
from typing import List, Optional
from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse
from pathlib import Path
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
    from . import get_model_manager
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
    from . import get_model_manager
    mm = get_model_manager()
    success = mm.delete_model(filename)
    if success:
        return {"success": True, "message": f"已删除 {filename}"}
    else:
        return {"success": False, "message": "删除失败"}

@router.post("/symlinks")
async def create_symlinks(models: Optional[List[str]] = Body(None)):
    """创建所有或指定模型的软链接"""
    from . import get_model_manager
    mm = get_model_manager()
    
    if models and len(models) > 0:
        # 为指定模型创建软链接
        success_count = 0
        failed_models = []
        all_local = mm.get_local_models()
        for model_name in models:
            found = False
            for m in all_local:
                if m['name'] == model_name:
                    file_path = Path(m['path'])
                    rel_path = file_path.relative_to(mm.models_dir)
                    parts = rel_path.parts
                    if len(parts) >= 2:
                        model_id = parts[0].replace('_', '/')
                        filename = parts[-1]
                    else:
                        model_id = "unknown"
                        filename = parts[0]
                    if mm.create_symlink_for_file(model_id, filename, file_path):
                        success_count += 1
                        found = True
                        break
            if not found:
                failed_models.append(model_name)
        return {"success": True, "message": f"已创建 {success_count}/{len(models)} 个软链接", "count": success_count, "failed": failed_models}
    else:
        count = mm.create_symlinks()
        return {"success": True, "message": f"已创建 {count} 个软链接", "count": count}

@router.get("/symlinks-list")
async def list_symlinks():
    """获取软链接目录中的文件列表"""
    import traceback
    from . import get_model_manager
    
    try:
        mm = get_model_manager()
        symlink_files = []
        links_dir = mm.links_dir
        
        if links_dir.exists():
            for name in sorted(os.listdir(str(links_dir))):
                file_path = links_dir / name
                # 使用 lexists 而非 isfile：isfile 会跟随软链接，
                # 若目标文件不存在（断链）则返回 False，导致条目被过滤
                if os.path.lexists(str(file_path)):
                    symlink_files.append({
                        'name': name,
                        'path': str(file_path),
                        'is_symlink': os.path.islink(str(file_path)),
                    })
        
        return {"success": True, "symlinks": symlink_files}
    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] list_symlinks 失败: {error_detail}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {"success": False, "error": error_detail, "symlinks": []}