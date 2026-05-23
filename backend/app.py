#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
import subprocess
import os
import time


# 动态获取 backend 目录路径，支持本地开发和服务器部署
sys.path.append(str(Path(__file__).parent))
from installer import LlamaCppInstaller
from routers import download_router, local_router, progress_router, system_router, set_model_manager
from model_manager import ModelManager
from config import PROJECT_DIR, LOGS_DIR, ensure_dirs

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

# 创建全局单例 ModelManager 并设置到路由模块
model_manager = ModelManager()
set_model_manager(model_manager)

# 注册路由
app.include_router(download_router)
app.include_router(local_router)
app.include_router(progress_router)
app.include_router(system_router)

# 更新 LlamaPanel 的函数
def update_llamapanel():
    """更新 LlamaPanel 自身"""
    log_file = LOGS_DIR / "update.log"
    log_file.parent.mkdir(exist_ok=True)
    
    def log_msg(msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    try:
        log_msg("========== 开始更新 LlamaPanel ==========")
        
        repo_path = str(PROJECT_DIR)
        
        log_msg(f"当前工作目录: {os.getcwd()}")
        log_msg(f"项目目录: {repo_path}")
        
        git_check = subprocess.run(['which', 'git'], capture_output=True, text=True)
        log_msg(f"git 路径: {git_check.stdout.strip()}")
        
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
        
        if result.returncode != 0:
            log_msg("git pull 失败，尝试 git fetch")
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            log_msg(f"git fetch 返回码: {fetch_result.returncode}")
            if fetch_result.stdout:
                log_msg(f"fetch 输出: {fetch_result.stdout}")
        
        log_msg("代码更新完成")
        
        requirements_file = PROJECT_DIR / "requirements.txt"
        if requirements_file.exists():
            log_msg("检查 Python 依赖...")
            pip_result = subprocess.run(
                [str(PROJECT_DIR / "venv/bin/pip"), 'install', '-r', 'requirements.txt'],
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
        if restart_result.stderr:
            log_msg(f"重启错误: {restart_result.stderr}")
        
        log_msg("========== 更新完成 ==========")
        return True
    except Exception as e:
        log_msg(f"更新失败: {e}")
        import traceback
        log_msg(traceback.format_exc())
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
            <a onclick="showPage('download')" id="navDownload">📥 模型下载</a>
            <a onclick="showPage('local')" id="navLocal">💾 本地模型</a>
            <a onclick="showPage('system')" id="navSystem">📋 系统信息</a>
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
        
        <!-- 模型下载页面容器 -->
        <div id="downloadPage" class="page-content hidden">
            <iframe src="/api/download/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
        
        <!-- 本地模型页面容器 -->
        <div id="localPage" class="page-content hidden">
            <iframe src="/api/local/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
        
        <!-- 系统信息页面容器 -->
        <div id="systemPage" class="page-content hidden">
            <iframe src="/api/system/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        let statusInterval = null;
        
        // 页面切换函数
        function showPage(page) {
            const homePage = document.getElementById('homePage');
            const downloadPage = document.getElementById('downloadPage');
            const localPage = document.getElementById('localPage');
            const systemPage = document.getElementById('systemPage');
            const navHome = document.getElementById('navHome');
            const navDownload = document.getElementById('navDownload');
            const navLocal = document.getElementById('navLocal');
            const navSystem = document.getElementById('navSystem');
            
            // 隐藏所有页面
            homePage.classList.add('hidden');
            downloadPage.classList.add('hidden');
            localPage.classList.add('hidden');
            systemPage.classList.add('hidden');
            
            // 移除所有 active 状态
            navHome.classList.remove('active');
            navDownload.classList.remove('active');
            navLocal.classList.remove('active');
            navSystem.classList.remove('active');
            
            if (page === 'home') {
                homePage.classList.remove('hidden');
                navHome.classList.add('active');
                refreshStatus();
                refreshLog();
            } else if (page === 'download') {
                downloadPage.classList.remove('hidden');
                navDownload.classList.add('active');
                const iframe = document.querySelector('#downloadPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            } else if (page === 'local') {
                localPage.classList.remove('hidden');
                navLocal.classList.add('active');
                const iframe = document.querySelector('#localPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            } else if (page === 'system') {
                systemPage.classList.remove('hidden');
                navSystem.classList.add('active');
                const iframe = document.querySelector('#systemPage iframe');
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
            if (confirm('🔄 更新 LlamaPanel 面板？\n\n将从 GitHub 拉取最新代码并更新依赖。\n如果系统配置了 NOPASSWD sudo，服务将自动重启。\n继续吗？')) {
                const btn = document.getElementById('updatePanelBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 更新中...';
                try {
                    const result = await fetchAPI('/api/update_panel', 'POST');
                    // 构建详细的提示信息
                    let msg = result.message;
                    if (result.log) {
                        // 提取日志最后几行
                        const lines = result.log.trim().split('\n');
                        const lastLines = lines.slice(-5).join('\n');
                        msg += '\n\n--- 最近日志 ---\n' + lastLines;
                    }
                    if (result.success) {
                        alert('✅ ' + msg);
                        // 如果提示需要手动重启或已经是最新，不自动刷新
                        if (msg.includes('手动重启') || msg.includes('已经是最新版本')) {
                            // 不自动刷新
                        } else {
                            setTimeout(() => {
                                location.reload();
                            }, 5000);
                        }
                    } else {
                        alert('❌ ' + msg);
                    }
                } catch(e) {
                    alert('❌ 更新失败: ' + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerHTML = '🔄 更新 LlamaPanel';
                }
            }
        }
        
        function startMonitoring() {
            // 安装/编译开始后，立即刷新一次状态
            refreshStatus();
        }
        
        // 初始化
        refreshStatus();
        refreshLog();
        startAutoRefresh();
        bindAutoRefreshCheckbox();
        // 统一使用5秒间隔刷新状态（避免多个定时器冲突）
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

def _read_log_safe(log_path: Path) -> str:
    """安全读取日志文件，避免编码问题"""
    try:
        return log_path.read_text(encoding='utf-8')
    except Exception:
        try:
            return log_path.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return "（无法读取日志文件）"

def _try_restart_service(log_msg) -> str:
    """尝试重启 LlamaPanel 服务（避免 sudo 挂起）"""
    import shutil
    
    # 方案1：尝试 sudo -n（非交互式），不会挂起
    sudo_path = shutil.which('sudo')
    if sudo_path:
        log_msg("方案1: 尝试 sudo -n systemctl restart llamapanel（非交互式）")
        try:
            r = subprocess.run(
                [sudo_path, '-n', 'systemctl', 'restart', 'llamapanel'],
                capture_output=True, text=True, timeout=15
            )
            log_msg(f"返回码: {r.returncode}")
            if r.stderr:
                log_msg(f"错误: {r.stderr.strip()}")
            if r.returncode == 0:
                log_msg("✅ 服务重启成功")
                return "✅ 更新成功！服务正在重启..."
        except subprocess.TimeoutExpired:
            log_msg("⏱️ sudo -n 超时（可能需要密码），跳过")
        except Exception as e:
            log_msg(f"sudo -n 异常: {e}")
    else:
        log_msg("⚠️ 未找到 sudo 命令")
    
    # 方案2：尝试 systemctl --user（用户级服务）
    log_msg("方案2: 尝试 systemctl --user restart llamapanel")
    try:
        r2 = subprocess.run(
            ['systemctl', '--user', 'restart', 'llamapanel'],
            capture_output=True, text=True, timeout=15
        )
        log_msg(f"返回码: {r2.returncode}")
        if r2.stderr:
            log_msg(f"错误: {r2.stderr.strip()}")
        if r2.returncode == 0:
            log_msg("✅ 用户级服务重启成功")
            return "✅ 更新成功！服务正在重启..."
    except subprocess.TimeoutExpired:
        log_msg("⏱️ systemctl --user 超时")
    except Exception as e:
        log_msg(f"systemctl --user 异常: {e}")
    
    # 方案3：尝试直接 systemctl restart（不带 sudo，可能因为 NOPASSWD 或 root 用户而成功）
    log_msg("方案3: 尝试直接 systemctl restart llamapanel（无 sudo）")
    try:
        r3 = subprocess.run(
            ['systemctl', 'restart', 'llamapanel'],
            capture_output=True, text=True, timeout=15
        )
        log_msg(f"返回码: {r3.returncode}")
        if r3.stderr:
            log_msg(f"错误: {r3.stderr.strip()}")
        if r3.returncode == 0:
            log_msg("✅ 直接重启成功")
            return "✅ 更新成功！服务正在重启..."
    except subprocess.TimeoutExpired:
        log_msg("⏱️ 直接重启超时")
    except Exception as e:
        log_msg(f"直接重启异常: {e}")
    
    # 全部失败：提示用户手动重启
    log_msg("⚠️ 所有自动重启方式均失败，请手动重启服务")
    return "✅ 更新成功！请手动重启 LlamaPanel 服务（sudo systemctl restart llamapanel）"

@app.post("/api/update_panel")
async def update_panel():
    """更新 LlamaPanel 自身（同步执行，返回实际结果）"""
    import platform
    log_file = LOGS_DIR / "update.log"
    log_file.parent.mkdir(exist_ok=True)
    
    def log_msg(msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    
    is_windows = platform.system() == "Windows"
    log_msg(f"操作系统: {platform.system()} {platform.release()}")
    
    try:
        log_msg("========== 开始更新 LlamaPanel ==========")
        repo_path = str(PROJECT_DIR)
        log_msg(f"项目目录: {repo_path}")
        
        # 检查 .git 目录
        git_dir = os.path.join(repo_path, '.git')
        if not os.path.isdir(git_dir):
            log_msg("❌ 未找到 .git 目录，不是 git 仓库")
            return {"success": False, "message": "未找到 .git 目录，无法使用 git 更新",
                    "log": _read_log_safe(log_file)}
        log_msg("✅ .git 目录存在")
        
        # ---- 第1步：获取当前分支名（用于后续 reset）----
        log_msg("检测当前分支...")
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
        log_msg(f"当前分支: {current_branch}")
        
        # ---- 第2步：先 stash 本地未提交的更改 ----
        log_msg("执行: git stash push -m 'llamapanel-auto-stash'")
        stash_result = subprocess.run(
            ['git', 'stash', 'push', '-m', 'llamapanel-auto-stash'],
            cwd=repo_path, capture_output=True, text=True, timeout=30
        )
        # 判断是否有本地修改被暂存：returncode==0 且输出不包含 "No local changes"
        stash_stdout = stash_result.stdout.strip()
        had_local_changes = (
            stash_result.returncode == 0
            and "No local changes to save" not in stash_stdout
            and stash_stdout != ""
        )
        log_msg(f"stash 返回码: {stash_result.returncode}")
        if stash_stdout:
            log_msg(f"stash 输出: {stash_stdout}")
        if had_local_changes:
            log_msg("📦 已暂存本地修改，更新完成后将恢复")
        else:
            log_msg("ℹ️ 没有需要暂存的本地修改")
        
        # ---- 第3步：执行 git pull ----
        log_msg("执行: git pull")
        pull_result = subprocess.run(
            ['git', 'pull'],
            cwd=repo_path, capture_output=True, text=True, timeout=60
        )
        log_msg(f"git pull 返回码: {pull_result.returncode}")
        if pull_result.stdout:
            log_msg(f"输出: {pull_result.stdout.strip()}")
        if pull_result.stderr:
            log_msg(f"错误: {pull_result.stderr.strip()}")
        
        # ---- 第4步：判断 pull 结果 ----
        pull_ok = (pull_result.returncode == 0)
        already_up_to_date = "Already up to date" in pull_result.stdout
        
        if pull_ok:
            log_msg("✅ git pull 成功")
            # pull 成功时，判断是否真的有新代码
            actually_updated = not already_up_to_date
        else:
            log_msg("⚠️ git pull 失败，尝试 git fetch + reset --hard 降级方案")
            log_msg("执行: git fetch origin")
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=repo_path, capture_output=True, text=True, timeout=60
            )
            log_msg(f"fetch 返回码: {fetch_result.returncode}")
            if fetch_result.stdout:
                log_msg(f"fetch 输出: {fetch_result.stdout.strip()}")
            if fetch_result.stderr:
                log_msg(f"fetch 错误: {fetch_result.stderr.strip()}")
            
            if fetch_result.returncode != 0:
                return {
                    "success": False,
                    "message": f"git pull 失败且 git fetch 也失败，请检查网络/权限",
                    "log": _read_log_safe(log_file)
                }
            
            # reset 到远程跟踪分支（动态使用当前分支名）
            remote_branch = f"origin/{current_branch}"
            log_msg(f"执行: git reset --hard {remote_branch}")
            reset_result = subprocess.run(
                ['git', 'reset', '--hard', remote_branch],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            log_msg(f"reset 返回码: {reset_result.returncode}")
            if reset_result.stdout:
                log_msg(f"reset 输出: {reset_result.stdout.strip()}")
            
            if reset_result.returncode == 0:
                log_msg(f"✅ git fetch + reset --hard {remote_branch} 成功")
                # 降级分支走完后，视为有新代码（因为 pull 失败后被强制重置了）
                actually_updated = True
            else:
                log_msg("❌ git reset 也失败")
                return {
                    "success": False,
                    "message": f"git pull 和 git reset --hard {remote_branch} 均失败，请手动检查",
                    "log": _read_log_safe(log_file)
                }
        
        # ---- 第5步：恢复 stash 的本地修改 ----
        if pull_ok and had_local_changes:
            log_msg("执行: git stash pop")
            pop_result = subprocess.run(
                ['git', 'stash', 'pop'],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            log_msg(f"stash pop 返回码: {pop_result.returncode}")
            if pop_result.stdout:
                log_msg(f"stash pop 输出: {pop_result.stdout.strip()}")
            if pop_result.returncode != 0:
                log_msg("⚠️ 恢复本地修改时出现冲突，请手动解决后执行 'git stash drop'")
        
        # 如果在降级分支中 stash 了但 pull 失败走了 reset，stash 已被 reset 清除，不需要 pop
        
        # 记录最新提交
        head_result = subprocess.run(
            ['git', 'log', '--oneline', '-1'],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        latest_commit = head_result.stdout.strip() if head_result.returncode == 0 else "未知"
        log_msg(f"当前最新提交: {latest_commit}")
        
        if actually_updated:
            log_msg("✅ 检测到新代码，正在安装依赖...")
        else:
            log_msg("ℹ️ 已经是最新版本")
        
        # ---- 第6步：安装/更新 Python 依赖 ----
        requirements_file = PROJECT_DIR / "requirements.txt"
        if requirements_file.exists() and actually_updated:
            if is_windows:
                pip_candidates = [
                    PROJECT_DIR / "venv" / "Scripts" / "pip.exe",
                    PROJECT_DIR / "venv" / "Scripts" / "pip3.exe",
                    PROJECT_DIR / ".venv" / "Scripts" / "pip.exe",
                    PROJECT_DIR / ".venv" / "Scripts" / "pip3.exe",
                ]
            else:
                pip_candidates = [
                    PROJECT_DIR / "venv/bin/pip",
                    PROJECT_DIR / ".venv/bin/pip",
                    PROJECT_DIR / "venv/bin/pip3",
                    PROJECT_DIR / ".venv/bin/pip3",
                ]
            
            pip_path = None
            for p in pip_candidates:
                if p.exists():
                    pip_path = p
                    break
            
            if pip_path:
                log_msg(f"使用 pip: {pip_path}")
                log_msg("安装/更新 Python 依赖...")
                pip_result = subprocess.run(
                    [str(pip_path), 'install', '-r', str(requirements_file)],
                    cwd=repo_path, capture_output=True, text=True, timeout=120
                )
                log_msg(f"pip 返回码: {pip_result.returncode}")
                if pip_result.stdout:
                    for line in pip_result.stdout.split('\n'):
                        line_s = line.strip()
                        if line_s and ('Successfully' in line_s or 'Installing' in line_s or 'ERROR' in line_s.upper()):
                            log_msg(f"pip: {line_s}")
                if pip_result.stderr:
                    for line in pip_result.stderr.split('\n'):
                        if 'ERROR' in line.upper() or 'error' in line.lower():
                            log_msg(f"pip 错误: {line.strip()}")
                if pip_result.returncode == 0:
                    log_msg("✅ Python 依赖安装完成")
                else:
                    log_msg("⚠️ pip 安装返回非零，但可能部分依赖已安装")
            else:
                log_msg("⚠️ 未找到虚拟环境的 pip，尝试系统 pip3...")
                try:
                    pip_result = subprocess.run(
                        ['pip3', 'install', '-r', str(requirements_file)],
                        cwd=repo_path, capture_output=True, text=True, timeout=120
                    )
                    log_msg(f"系统 pip3 返回码: {pip_result.returncode}")
                except FileNotFoundError:
                    log_msg("⚠️ 系统 pip3 不可用，跳过依赖安装")
        else:
            if not actually_updated:
                log_msg("ℹ️ 无新代码，跳过依赖安装")
        
        log_msg("========== 更新完成 ==========")
        log_content = _read_log_safe(log_file)
        
        # ---- 第7步：重启服务 ----
        if not actually_updated:
            # 没有新代码，不需要重启
            return {
                "success": True,
                "message": "✅ 已经是最新版本，无需重启",
                "log": log_content
            }
        
        if is_windows:
            log_msg("ℹ️ Windows 下请手动重启服务")
            restart_message = "✅ 更新成功！请手动重启 LlamaPanel 服务"
        else:
            # Linux：尝试多种重启方式，避免 sudo 挂起
            restart_message = _try_restart_service(log_msg)
        
        return {
            "success": True,
            "message": restart_message,
            "log": log_content
        }
        
    except subprocess.TimeoutExpired as e:
        err_msg = f"操作超时: {e}"
        log_msg(f"❌ {err_msg}")
        return {"success": False, "message": err_msg, "log": _read_log_safe(log_file)}
    except Exception as e:
        log_msg(f"❌ 更新失败: {e}")
        import traceback
        log_msg(traceback.format_exc())
        return {"success": False, "message": f"更新失败: {str(e)}", "log": _read_log_safe(log_file)}

if __name__ == "__main__":
    import uvicorn
    print("🦙 LlamaPanel 启动中...")
    print("访问地址: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)