#!/usr/bin/env python3
import os
import shutil
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
        # 为指定模型创建软链接（直接用 path 创建，避免 name 匹配问题）
        success_count = 0
        failed_models = []
        for model_path_str in models:
            try:
                file_path = Path(model_path_str)
                if not file_path.exists():
                    failed_models.append(model_path_str)
                    continue
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
                else:
                    failed_models.append(model_path_str)
            except Exception as e:
                failed_models.append(model_path_str)
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
            for root, dirs, files in os.walk(str(links_dir)):
                for entry in sorted(dirs + files):
                    entry_path = os.path.join(root, entry)
                    rel_path = os.path.relpath(entry_path, str(links_dir))
                    if os.path.lexists(entry_path):
                        symlink_files.append({
                            'name': rel_path,
                            'path': entry_path,
                            'is_symlink': os.path.islink(entry_path),
                            'is_dir': os.path.isdir(entry_path) and not os.path.islink(entry_path),
                        })
        
        return {"success": True, "symlinks": symlink_files}
    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] list_symlinks 失败: {error_detail}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {"success": False, "error": error_detail, "symlinks": []}

@router.delete("/symlink-delete")
async def delete_symlink(filename: str):
    """删除指定软链接文件或目录（支持子目录中的路径）"""
    import traceback
    from . import get_model_manager
    try:
        mm = get_model_manager()
        # 安全检查：禁止路径遍历和绝对路径
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            return {"success": False, "message": f"非法路径: {filename}"}
        link_path = mm.links_dir / filename
        # 二次确认：确保拼接后的绝对路径仍在 links_dir 内（不跟随软链接）
        link_path_abs = link_path.absolute()
        links_dir_abs = mm.links_dir.absolute()
        if not str(link_path_abs).startswith(str(links_dir_abs) + os.sep) and link_path_abs != links_dir_abs:
            return {"success": False, "message": f"非法路径: {filename}"}
        link_path = link_path_abs
        if not os.path.lexists(str(link_path)):
            return {"success": False, "message": f"软链接 {filename} 不存在"}
        if os.path.isdir(str(link_path)) and not os.path.islink(str(link_path)):
            shutil.rmtree(str(link_path))
            return {"success": True, "message": f"已删除目录 {filename}"}
        else:
            os.unlink(str(link_path))
            return {"success": True, "message": f"已删除 {filename}"}
    except Exception as e:
        error_detail = f"{type(e).__name__}: {str(e)}"
        print(f"[ERROR] delete_symlink 失败: {error_detail}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {"success": False, "message": f"删除失败: {error_detail}"}