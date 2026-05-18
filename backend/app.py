#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
import subprocess
sys.path.append('/opt/llamapanel/backend')
from installer import LlamaCppInstaller
from models_page import router as models_router

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

# 注册模型管理路由
app.include_router(models_router)

# 更新 LlamaPanel 的函数
def update_llamapanel():
    """更新 LlamaPanel 自身"""
    import time
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
        
        # 进入项目目录
        os.chdir("/opt/llamapanel")
        log_msg("进入目录: /opt/llamapanel")
        
        # 拉取最新代码
        log_msg("执行: git pull")
        result = subprocess.run(['git', 'pull'], capture_output=True, text=True, timeout=60)
        if result.stdout:
            log_msg(f"输出: {result.stdout}")
        if result.stderr:
            log_msg(f"错误: {result.stderr}")
        
        if result.returncode != 0:
            log_msg("git pull 失败")
            return False
        
        log_msg("代码更新完成")
        
        # 检查是否有依赖更新
        log_msg("检查 Python 依赖...")
        subprocess.run(['/opt/llamapanel/venv/bin/pip', 'install', '-r', 'requirements.txt'], 
                       capture_output=True, text=True, timeout=120)
        
        # 重启服务
        log_msg("重启 LlamaPanel 服务...")
        subprocess.run(['sudo', 'systemctl', 'restart', 'llamapanel'], capture_output=True, timeout=30)
        
        log_msg("========== 更新完成 ==========")
        return True
    except Exception as e:
        log_msg(f"更新失败: {e}")
        return False

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LlamaPanel - llama.cpp 管理面板</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .nav-bar {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .nav-bar a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 8px;
            background: rgba(255,255,255,0.2);
            transition: all 0.3s;
            cursor: pointer;
        }
        .nav-bar a:hover {
            background: rgba(255,255,255,0.3);
        }
        .nav-bar a.active {
            background: white;
            color: #667eea;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 { color: #333; margin-bottom: 8px; }
        .subtitle { color: #666; margin-bottom: 24px; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-ok { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-building { background: #cce5ff; color: #004085; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-right: 10px;
            margin-bottom: 10px;
            transition: all 0.3s;
        }
        button:hover { background: #5a67d8; transform: translateY(-1px); }
        button.danger { background: #e53e3e; }
        button.danger:hover { background: #c53030; }
        button.success { background: #38a169; }
        button.success:hover { background: #2f855a; }
        button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .log-viewer {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            padding: 16px;
            border-radius: 8px;
            height: 400px;
            overflow-y: auto;
            font-size: 12px;
        }
        .log-line {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 3px 5px;
            border-bottom: 1px solid #2a2a2a;
            white-space: pre-wrap;
            word-break: break-all;
            margin: 0;
        }
        .log-empty {
            height: 5px;
            border-bottom: none;
        }
        .log-error {
            color: #ff6b6b;
            background-color: rgba(255, 107, 107, 0.1);
        }
        .log-warning {
            color: #ffd93d;
        }
        .log-success {
            color: #6bcb77;
        }
        .log-command {
            color: #4d9de0;
        }
        .log-separator {
            color: #c9c9c9;
            font-weight: bold;
            border-bottom: 1px solid #555;
            margin: 5px 0;
            background-color: #2a2a2a;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .info-item {
            background: #f7fafc;
            padding: 12px;
            border-radius: 8px;
        }
        .info-label { font-size: 12px; color: #718096; margin-bottom: 4px; }
        .info-value { font-size: 16px; font-weight: 600; color: #2d3748; word-break: break-all; }
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #e2e8f0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .log-controls { margin-bottom: 10px; display: flex; gap: 10px; align-items: center; }
        .auto-refresh { font-size: 12px; color: #666; display: flex; align-items: center; gap: 5px; }
        hr { margin: 15px 0; border: none; border-top: 1px solid #e2e8f0; }
        
        .log-viewer::-webkit-scrollbar {
            width: 8px;
        }
        .log-viewer::-webkit-scrollbar-track {
            background: #1e1e1e;
            border-radius: 4px;
        }
        .log-viewer::-webkit-scrollbar-thumb {
            background: #555;
            border-radius: 4px;
        }
        .log-viewer::-webkit-scrollbar-thumb:hover {
            background: #777;
        }
        .page-content {
            transition: opacity 0.3s ease;
        }
        .hidden {
            display: none;
        }
        .button-group {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-bar">
            <a onclick="showPage('home')" id="navHome" class="active">🏠 主页</a>
            <a onclick="showPage('models')" id="navModels">📦 模型管理</a>
        </div>
        
        <!-- 主页内容 -->
        <div id="homePage" class="page-content">
            <div class="card">
                <h1>🦙 LlamaPanel</h1>
                <p class="subtitle">llama.cpp 图形化管理面板 - 无需命令行</p>
                
                <div class="button-group">
                    <button onclick="installLlama()" id="installBtn">🚀 完整安装 llama.cpp</button>
                    <button onclick="updateLlama()" id="updateBtn">🔄 更新llama.cpp</button>
                    <button onclick="rebuildLlama()" id="rebuildBtn">🔨 重新编译</button>
                    <button onclick="cleanBuild()" class="danger" id="cleanBtn">🧹 清理编译</button>
                    <button onclick="deleteAll()" class="danger" id="deleteBtn">🗑️ 删除所有</button>
                    <button onclick="updateLlamaPanel()" class="success" id="updatePanelBtn">🔄 更新 LlamaPanel</button>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 安装状态</h2>
                <div id="statusInfo">
                    <div class="loading"></div> 加载中...
                </div>
            </div>
            
            <div class="card">
                <h2>📋 安装日志</h2>
                <div class="log-controls">
                    <button onclick="refreshLog()" style="margin-bottom: 0;">🔄 刷新</button>
                    <label class="auto-refresh">
                        <input type="checkbox" id="autoRefresh"> 自动刷新 (2秒)
                    </label>
                </div>
                <div id="logContent" class="log-viewer">
                    加载日志中...
                </div>
            </div>
        </div>
        
        <!-- 模型管理页面容器（iframe 方式） -->
        <div id="modelsPage" class="page-content hidden">
            <iframe src="/models" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        let statusInterval = null;
        
        // 页面切换函数
        function showPage(page) {
            const homePage = document.getElementById('homePage');
            const modelsPage = document.getElementById('modelsPage');
            const navHome = document.getElementById('navHome');
            const navModels = document.getElementById('navModels');
            
            if (page === 'home') {
                homePage.classList.remove('hidden');
                modelsPage.classList.add('hidden');
                navHome.classList.add('active');
                navModels.classList.remove('active');
                refreshStatus();
                refreshLog();
            } else {
                homePage.classList.add('hidden');
                modelsPage.classList.remove('hidden');
                navHome.classList.remove('active');
                navModels.classList.add('active');
                const iframe = document.querySelector('#modelsPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            }
        }
        
        function startAutoRefresh() {
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(() => {
                const chk = document.getElementById('autoRefresh');
                if (chk && chk.checked === true) {
                    refreshLog();
                }
            }, 2000);
        }
        
        function bindAutoRefreshCheckbox() {
            const chk = document.getElementById('autoRefresh');
            if (chk) {
                chk.addEventListener('change', function() {
                    if (this.checked) {
                        if (autoRefreshInterval) clearInterval(autoRefreshInterval);
                        autoRefreshInterval = setInterval(() => {
                            const c = document.getElementById('autoRefresh');
                            if (c && c.checked === true) {
                                refreshLog();
                            }
                        }, 2000);
                    } else {
                        if (autoRefreshInterval) {
                            clearInterval(autoRefreshInterval);
                            autoRefreshInterval = null;
                        }
                    }
                });
            }
        }
        
        async function fetchAPI(endpoint, method='GET', data=null) {
            const options = { method: method };
            if (data && method === 'POST') {
                options.headers = { 'Content-Type': 'application/json' };
                options.body = JSON.stringify(data);
            }
            const response = await fetch(endpoint, options);
            return await response.json();
        }
        
        async function refreshStatus() {
            try {
                const status = await fetchAPI('/api/status');
                const info = document.getElementById('statusInfo');
                if (!info) return;
                
                let buildStatusHtml = '';
                let buildStatusClass = '';
                
                if (status.built) {
                    buildStatusHtml = '✅ 已编译';
                    buildStatusClass = 'status-ok';
                } else if (status.building) {
                    buildStatusHtml = '⏳ ' + (status.building_progress || '编译中...');
                    buildStatusClass = 'status-building';
                } else {
                    buildStatusHtml = '❌ 未编译';
                    buildStatusClass = 'status-warning';
                }
                
                let currentVersionText = status.version || '未知';
                let latestVersionHtml = '';
                
                if (status.has_update && status.latest_version) {
                    latestVersionHtml = `<div class="info-value" style="color: #e53e3e; font-size: 14px; margin-top: 5px;">
                                            ⚠️ 最新版本: ${status.latest_version} (点击「更新版本」)
                                        </div>`;
                } else if (status.latest_version) {
                    latestVersionHtml = `<div class="info-value" style="color: #6bcb77; font-size: 14px; margin-top: 5px;">
                                            ✅ 已是最新版本: ${status.latest_version}
                                        </div>`;
                } else {
                    latestVersionHtml = `<div class="info-value" style="color: #888; font-size: 14px; margin-top: 5px;">
                                            📡 正在检查更新...
                                        </div>`;
                }
                
                info.innerHTML = `
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">克隆状态</div>
                            <div class="info-value">${status.cloned ? '✅ 已克隆' : '❌ 未克隆'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">编译状态</div>
                            <div class="info-value"><span class="status-badge ${buildStatusClass}">${buildStatusHtml}</span></div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">llama.cpp 路径</div>
                            <div class="info-value">${status.llama_dir || '未设置'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">llama-server 路径</div>
                            <div class="info-value">${status.server_path || (status.building ? '⏳ 编译中...' : '未编译')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">当前版本</div>
                            <div class="info-value">${currentVersionText}</div>
                            <div class="info-label" style="margin-top: 8px;">最新版本</div>
                            ${latestVersionHtml}
                        </div>
                    </div>
                `;
            } catch(e) {
                console.error('刷新状态失败:', e);
            }
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function refreshLog() {
            try {
                const response = await fetch('/api/log');
                let text = await response.text();
                const logDiv = document.getElementById('logContent');
                if (!logDiv) return;
                
                if (!text || text === '暂无日志' || text.trim() === '') {
                    logDiv.innerHTML = '<div class="log-line">暂无日志，请点击"完整安装"开始安装</div>';
                    return;
                }
                
                let processed = text.replace(/\\\\n/g, '\\n');
                processed = processed.replace(/\\\\r\\\\n/g, '\\n');
                
                const lines = processed.split('\\n');
                
                let html = '';
                for (let i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (line.trim() === '') continue;
                    
                    let lineClass = 'log-line';
                    let displayLine = escapeHtml(line);
                    
                    if (line.includes('[ERR]') || line.includes('error') || line.includes('Error')) {
                        lineClass += ' log-error';
                        displayLine = '❌ ' + displayLine;
                    } else if (line.includes('✅')) {
                        lineClass += ' log-success';
                    } else if (line.includes('⚠️') || line.includes('Warning')) {
                        lineClass += ' log-warning';
                        displayLine = '⚠️ ' + displayLine;
                    } else if (line.includes('执行:')) {
                        lineClass += ' log-command';
                        displayLine = '🔧 ' + displayLine;
                    } else if (line.includes('==========')) {
                        lineClass += ' log-separator';
                    } else if (line.includes('完成') || line.includes('成功')) {
                        lineClass += ' log-success';
                    }
                    
                    html += `<div class="${lineClass}">${displayLine}</div>`;
                }
                
                if (html === '') {
                    logDiv.innerHTML = '<div class="log-line">暂无日志内容</div>';
                } else {
                    logDiv.innerHTML = html;
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
            } catch(e) {
                console.error('刷新日志失败:', e);
                const logDiv = document.getElementById('logContent');
                if (logDiv) logDiv.innerHTML = '加载日志失败: ' + e.message;
            }
        }
        
        async function installLlama() {
            if (confirm('开始完整安装 llama.cpp？\\n这可能需要 10-30 分钟。')) {
                const btn = document.getElementById('installBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 安装中...';
                const result = await fetchAPI('/api/install', 'POST');
                alert(result.message);
                startMonitoring();
                btn.disabled = false;
                btn.innerHTML = '🚀 完整安装 llama.cpp';
            }
        }
        
        async function updateLlama() {
            if (confirm('更新 llama.cpp 到最新稳定版本？\\n这将切换代码到最新版本，然后需要重新编译。')) {
                const btn = document.getElementById('updateBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 更新中...';
                const result = await fetchAPI('/api/update', 'POST');
                alert(result.message);
                refreshStatus();
                btn.disabled = false;
                btn.innerHTML = '🔄 更新llama.cpp';
            }
        }
        
        async function rebuildLlama() {
            if (confirm('重新编译 llama.cpp？')) {
                const btn = document.getElementById('rebuildBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 编译中...';
                const result = await fetchAPI('/api/rebuild', 'POST');
                alert(result.message);
                refreshStatus();
                btn.disabled = false;
                btn.innerHTML = '🔨 重新编译';
            }
        }
        
        async function cleanBuild() {
            if (confirm('清理所有编译产物？')) {
                const result = await fetchAPI('/api/clean', 'POST');
                alert(result.message);
                refreshStatus();
            }
        }
        
        async function deleteAll() {
            if (confirm('⚠️ 警告：这将删除整个 llama.cpp 目录及其所有文件！\\n删除后需要重新点击「完整安装」。\\n确定要继续吗？')) {
                const btn = document.getElementById('deleteBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 删除中...';
                const result = await fetchAPI('/api/delete_all', 'POST');
                alert(result.message);
                refreshStatus();
                refreshLog();
                btn.disabled = false;
                btn.innerHTML = '🗑️ 删除所有';
            }
        }
        
        async function updateLlamaPanel() {
            if (confirm('更新 LlamaPanel 面板本身？\\n这将从 GitHub 拉取最新代码并重启服务。\\n服务重启后页面将重新加载。')) {
                const btn = document.getElementById('updatePanelBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 更新中...';
                try {
                    const result = await fetchAPI('/api/update_panel', 'POST');
                    alert(result.message);
                    if (result.success) {
                        setTimeout(() => {
                            location.reload();
                        }, 3000);
                    }
                } catch(e) {
                    alert('更新失败: ' + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '🔄 更新 LlamaPanel';
                }
            }
        }
        
        function startMonitoring() {
            if (statusInterval) clearInterval(statusInterval);
            statusInterval = setInterval(() => {
                refreshStatus();
            }, 3000);
            setTimeout(() => {
                if (statusInterval) clearInterval(statusInterval);
            }, 300000);
        }
        
        // 初始化
        refreshStatus();
        refreshLog();
        startAutoRefresh();
        bindAutoRefreshCheckbox();
        setInterval(refreshStatus, 5000);
    </script>
</body>
</html>
'''

@app.get("/")
async def root():
    return HTMLResponse(content=HTML_PAGE)

@app.get("/api/status")
async def get_status():
    return installer.get_status()

@app.get("/api/log")
async def get_log():
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
        finally:
            update_panel._running = False
    
    update_panel._running = False
    background_tasks.add_task(run_update)
    return {"success": True, "message": "LlamaPanel 更新任务已启动，服务将重启"}

if __name__ == "__main__":
    import uvicorn
    print("🦙 LlamaPanel 启动中...")
    print("访问地址: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)