@router.post("/api/pause")
async def pause_download(request: Request):
    """暂停下载"""
    data = await request.json()
    filename = data.get('filename')
    try:
        success = model_manager.pause_download(filename)
        return {"success": success, "message": "已暂停" if success else "暂停失败"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/api/stop")
async def stop_download(request: Request):
    """停止下载并删除部分文件"""
    data = await request.json()
    filename = data.get('filename')
    model_id = data.get('model_id', '')
    
    try:
        model_manager.stop_download(filename)
        time.sleep(0.5)
        
        # 删除部分下载文件
        file_path = model_manager.get_file_path(model_id, filename)
        partial_path = file_path.parent / (file_path.name + '.partial')
        if partial_path.exists():
            partial_path.unlink()
        
        model_manager.clear_progress(filename)
        return {"success": True, "message": "已停止下载"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.post("/api/resume")
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

@router.post("/api/cancel")
async def cancel_download(request: Request):
    """取消下载并删除部分文件"""
    data = await request.json()
    filename = data.get('filename')
    model_id = data.get('model_id', '')
    
    try:
        model_manager.stop_download(filename)
        time.sleep(0.5)
        
        # 删除部分下载文件
        file_path = model_manager.get_file_path(model_id, filename)
        partial_path = file_path.parent / (file_path.name + '.partial')
        if partial_path.exists():
            partial_path.unlink()
        
        model_manager.clear_progress(filename)
        return {"success": True, "message": "已取消下载"}
    except Exception as e:
        return {"success": False, "message": str(e)}