#!/usr/bin/env python3
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
from model_manager import ModelManager

router = APIRouter(prefix="/api/download", tags=["download"])
model_manager = ModelManager()

# 读取 HTML 文件
def read_html_file(filename):
    filepath = Path(__file__).parent.parent / "templates" / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>页面加载失败</h1>"

# 预加载 HTML 内容
DOWNLOAD_HTML = read_html_file("download.html")

@router.get("/page", response_class=HTMLResponse)
async def download_page():
    """模型下载页面"""
    return HTMLResponse(content=DOWNLOAD_HTML)

@router.get("/search")
async def search_models(q: str, limit: int = 30):
    """搜索 HuggingFace 模型"""
    results = model_manager.search_huggingface_models(q, limit)
    return {"success": True, "results": results}

@router.get("/files")
async def get_model_files(model_id: str):
    """获取模型的 GGUF 文件列表"""
    files = model_manager.get_model_files(model_id)
    return {"success": True, "files": files}

@router.post("/start")
async def start_download(request, background_tasks: BackgroundTasks):
    """开始下载模型"""
    data = await request.json()
    download_url = data.get('download_url')
    filename = data.get('filename')
    model_id = data.get('model_id', '')
    
    if not download_url or not filename:
        return {"success": False, "message": "缺少必要参数"}
    
    def run_download():
        model_manager.download_model(download_url, filename, model_id)
    
    background_tasks.add_task(run_download)
    return {"success": True, "message": f"开始下载 {filename}"}