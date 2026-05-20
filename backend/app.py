#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
import subprocess
import os
import time

sys.path.append('/opt/llamapanel/backend')
from installer import LlamaCppInstaller
from routers import download_router, local_router, progress_router

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

# 注册路由
app.include_router(download_router)
app.include_router(local_router)
app.include_router(progress_router)

# 读取 HTML 文件
def read_html_file(filename):
    filepath = Path(__file__).parent / "templates" / filename
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return f"<h1>File not found: {filename}</h1>"

# 预加载 HTML 内容
BASE_HTML = read_html_file("base.html")

@app.get("/")
async def root():
    """主页 - 返回基础框架"""
    return HTMLResponse(content=BASE_HTML)

@app.get("/api/page/{page_name}")
async def get_page(page_name: str):
    """获取页面内容"""
    if page_name == "home":
        content = read_html_file("home.html")
    elif page_name == "download":
        content = read_html_file("download.html")
    elif page_name == "local":
        content = read_html_file("local.html")
    else:
        return HTMLResponse(content="<div class='card'><div class='info-text'>页面不存在</div></div>", status_code=404)
    return HTMLResponse(content=content)

@app.get("/api/status")
async def get_status():
    """获取安装状态"""
    return installer.get_status()

@app.get("/api/log")
async def get_log():
    """获取安装日志"""
    log_file = installer.log_file
    if not log_file.exists():
        return "暂无日志"
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content or content.strip() == '':
        return "暂无日志"
    
    content = content.replace('\\n', '\n')
    content = content.replace('\\r\\n', '\n')
    return content

@app.post("/api/install")
async def install_llama(background_tasks: BackgroundTasks):
    """安装 llama.cpp"""
    if installer._install_running:
        return {"success": False, "message": "安装已在运行中"}
    def run_install():
        installer._install_running = True
        try:
            installer.full_install()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_install)
    return {"success": True, "message": "安装任务已启动，请查看日志面板"}

@app.post("/api/update")
async def update_llama(background_tasks: BackgroundTasks):
    """更新 llama.cpp"""
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_update():
        installer._install_running = True
        try:
            installer.update_llama_cpp()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_update)
    return {"success": True, "message": "更新任务已启动，请查看日志面板"}

@app.post("/api/rebuild")
async def rebuild_llama(background_tasks: BackgroundTasks):
    """重新编译"""
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_rebuild():
        installer._install_running = True
        try:
            installer.rebuild()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_rebuild)
    return {"success": True, "message": "重新编译任务已启动，请查看日志面板"}

@app.post("/api/clean")
async def clean_build(background_tasks: BackgroundTasks):
    """清理编译产物"""
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_clean():
        installer._install_running = True
        try:
            installer.clean_build()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_clean)
    return {"success": True, "message": "清理任务已启动，请查看日志面板"}

@app.post("/api/delete_all")
async def delete_all(background_tasks: BackgroundTasks):
    """删除所有"""
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_delete():
        installer._install_running = True
        try:
            installer.delete_all()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_delete)
    return {"success": True, "message": "删除任务已启动，请查看日志面板"}

@app.post("/api/update_panel")
async def update_panel(background_tasks: BackgroundTasks):
    """更新 LlamaPanel 自身"""
    if hasattr(update_panel, '_running') and update_panel._running:
        return {"success": False, "message": "更新任务已在运行中"}
    
    def run_update():
        update_panel._running = True
        try:
            update_llamapanel()
        except Exception as e:
            print(f"更新异常: {e}")
        finally:
            update_panel._running = False
    
    update_panel._running = False
    background_tasks.add_task(run_update)
    return {"success": True, "message": "LlamaPanel 更新任务已启动，请查看 /opt/llamapanel/logs/update.log"}

def update_llamapanel():
    """更新 LlamaPanel 自身"""
    log_file = Path("/opt/llamapanel/logs/update.log")
    log_file.parent.mkdir(exist_ok=True)
    
    def log_msg(msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    try:
        log_msg("========== 开始更新 LlamaPanel ==========")
        repo_path = "/opt/llamapanel"
        
        log_msg("执行: git pull")
        result = subprocess.run(
            ['git', 'pull'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        log_msg(f"git pull 返回码: {result.returncode}")
        if result.stdout:
            log_msg(f"输出: {result.stdout}")
        if result.stderr:
            log_msg(f"错误: {result.stderr}")
        
        log_msg("代码更新完成")
        
        requirements_file = Path(repo_path) / "requirements.txt"
        if requirements_file.exists():
            log_msg("检查 Python 依赖...")
            pip_result = subprocess.run(
                ['/opt/llamapanel/venv/bin/pip', 'install', '-r', 'requirements.txt'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=120
            )
            log_msg(f"pip 安装返回码: {pip_result.returncode}")
        
        log_msg("重启 LlamaPanel 服务...")
        restart_result = subprocess.run(
            ['sudo', 'systemctl', 'restart', 'llamapanel'],
            capture_output=True,
            text=True,
            timeout=30
        )
        log_msg(f"重启服务返回码: {restart_result.returncode}")
        
        log_msg("========== 更新完成 ==========")
        return True
    except Exception as e:
        log_msg(f"更新失败: {e}")
        import traceback
        log_msg(traceback.format_exc())
        return False

if __name__ == "__main__":
    import uvicorn
    print("🦙 LlamaPanel 启动中...")
    print("访问地址: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)