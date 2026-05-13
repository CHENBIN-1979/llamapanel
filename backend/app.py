#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
sys.path.append('/opt/llamapanel/backend')
from installer import LlamaCppInstaller

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

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
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🦙 LlamaPanel</h1>
            <p class="subtitle">llama.cpp 图形化管理面板 - 无需命令行</p>
            
            <div style="margin-top: 20px;">
                <button onclick="installLlama()" id="installBtn">🚀 完整安装 llama.cpp</button>
                <button onclick="updateLlama()" id="updateBtn">🔄 更新代码</button>
                <button onclick="rebuildLlama()" id="rebuildBtn">🔨 重新编译</button>
                <button onclick="cleanBuild()" class="danger" id="cleanBtn">🧹 清理编译</button>
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
                    <input type="checkbox" id="autoRefresh" checked> 自动刷新 (2秒)
                </label>
            </div>
            <div id="logContent" class="log-viewer">
                加载日志中...
            </div>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        
        function startAutoRefresh() {
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(() => {
                if (document.getElementById('autoRefresh').checked) {
                    refreshLog();
                }
            }, 2000);
        }
        
        async function fetchAPI(endpoint, method='GET') {
            const response = await fetch(endpoint, { method: method });
            return await response.json();
        }
        
        async function refreshStatus() {
            try {
                const status = await fetchAPI('/api/status');
                const info = document.getElementById('statusInfo');
                
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
                            <div class="info-label">状态</div>
                            <div class="info-value">${status.version || '未知'}</div>
                        </div>
                    </div>
                `;
            } catch(e) {
                console.error('刷新状态失败:', e);
            }
        }
        
        async function refreshLog() {
            try {
                const response = await fetch('/api/log');
                const text = await response.text();
                const logDiv = document.getElementById('logContent');
                
                // 直接按换行符分割（后端已经写入真正的 \\n）
                const lines = text.split(/\\r?\\n/);
                
                let html = '';
                for (let i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (line.trim() === '') {
                        if (i > 0 && i < lines.length - 1) {
                            html += '<div class="log-line log-empty">&nbsp;</div>';
                        }
                        continue;
                    }
                    
                    let lineClass = 'log-line';
                    let displayLine = escapeHtml(line);
                    
                    if (line.includes('[ERR]') || line.includes('error') || line.includes('Error') || line.includes('ERROR')) {
                        lineClass += ' log-error';
                        displayLine = '❌ ' + displayLine;
                    } else if (line.includes('✅')) {
                        lineClass += ' log-success';
                    } else if (line.includes('⚠️') || line.includes('Warning') || line.includes('warning')) {
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
                
                logDiv.innerHTML = html;
                logDiv.scrollTop = logDiv.scrollHeight;
            } catch(e) {
                console.error('刷新日志失败:', e);
                document.getElementById('logContent').innerHTML = '加载日志失败: ' + e.message;
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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
            if (confirm('更新 llama.cpp 到最新版本？')) {
                const result = await fetchAPI('/api/update', 'POST');
                alert(result.message);
                refreshStatus();
            }
        }
        
        async function rebuildLlama() {
            if (confirm('重新编译 llama.cpp？')) {
                const result = await fetchAPI('/api/rebuild', 'POST');
                alert(result.message);
                refreshStatus();
            }
        }
        
        async function cleanBuild() {
            if (confirm('清理所有编译产物？')) {
                const result = await fetchAPI('/api/clean', 'POST');
                alert(result.message);
                refreshStatus();
            }
        }
        
        function startMonitoring() {
            const interval = setInterval(() => {
                refreshStatus();
                refreshLog();
            }, 3000);
            setTimeout(() => clearInterval(interval), 300000);
        }
        
        refreshStatus();
        refreshLog();
        startAutoRefresh();
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
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "暂无日志"

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
async def update_llama():
    try:
        installer.update_llama_cpp()
        return {"success": True, "message": "代码更新完成"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/rebuild")
async def rebuild_llama():
    try:
        installer.rebuild()
        return {"success": True, "message": "重新编译完成"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/clean")
async def clean_build():
    try:
        installer.clean_build()
        return {"success": True, "message": "编译产物已清理"}
    except Exception as e:
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("🦙 LlamaPanel 启动中...")
    print("访问地址: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)