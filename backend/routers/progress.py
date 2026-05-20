#!/usr/bin/env python3
from fastapi import APIRouter, Request, BackgroundTasks
from model_manager import ModelManager

router = APIRouter(prefix="/api/progress", tags=["progress"])
model_manager = ModelManager()

@router.get("/status")
async def get_progress(filename: str):
    """获取下载进度"""
    progress = model_manager.get_progress(filename)
    return progress

@router.post("/pause")
async def pause_download(request: Request):
    """暂停下载"""
    data = await request.json()
    filename = data.get('filename')
    try:
        success = model_manager.pause_download(filename)
        return {"success": success, "message": "已暂停" if success else "暂停失败"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/resume")
async def resume_download(request: Request, background_tasks: BackgroundTasks):
    """恢复下载"""
    data = await request.json()
    download_url = data.get('download_url')
    filename = data.get('filename')
    model_id = data.get('model_id', '')
    
    if not download_url or not filename:
        return {"success": False, "message": "缺少必要参数"}
    
    def run_download():
        model_manager.download_model(download_url, filename, model_id)
    
    background_tasks.add_task(run_download)
    return {"success": True, "message": f"恢复下载 {filename}"}

@router.post("/delete_partial")
async def delete_partial(request: Request):
    """删除部分下载的文件"""
    import time
    data = await request.json()
    filename = data.get('filename')
    model_id = data.get('model_id', '')
    
    try:
        model_manager.stop_download(filename)
        time.sleep(0.5)
        
        file_path = model_manager.get_file_path(model_id, filename)
        partial_path = file_path.parent / (file_path.name + '.partial')
        if partial_path.exists():
            partial_path.unlink()
        
        if file_path.exists() and file_path.stat().st_size > 0:
            file_size = file_path.stat().st_size
            if file_size < 1024 * 1024:
                file_path.unlink()
        
        model_manager.clear_progress(filename)
        return {"success": True, "message": "已删除部分下载文件"}
    except Exception as e:
        return {"success": False, "message": str(e)}