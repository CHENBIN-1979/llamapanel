#!/usr/bin/env python3
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from model_manager import ModelManager

router = APIRouter(prefix="/models", tags=["models"])
model_manager = ModelManager()

# 模型管理页面的 HTML（不带导航栏）
MODELS_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LlamaPanel - 模型管理</title>
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
        .container { max-width: 1400px; margin: 0 auto; }
        .card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 { color: #333; margin-bottom: 8px; }
        h2 { color: #333; margin-bottom: 16px; font-size: 18px; }
        h3 { color: #555; margin-bottom: 12px; font-size: 16px; }
        .subtitle { color: #666; margin-bottom: 24px; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        button:hover { background: #5a67d8; transform: translateY(-1px); }
        button.danger { background: #e53e3e; }
        button.danger:hover { background: #c53030; }
        button.small { padding: 4px 12px; font-size: 12px; }
        input, select {
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid #ddd;
            font-size: 14px;
        }
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .search-box input {
            flex: 1;
            min-width: 200px;
        }
        .model-card {
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
            transition: all 0.3s;
        }
        .model-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .model-name {
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 5px;
            cursor: pointer;
            padding: 8px;
            background: #f7fafc;
            border-radius: 8px;
            transition: background 0.3s;
        }
        .model-name:hover {
            background: #edf2f7;
        }
        .model-meta {
            font-size: 12px;
            color: #718096;
            margin-bottom: 10px;
            padding-left: 8px;
        }
        .file-list {
            margin-top: 12px;
            border-top: 1px solid #e2e8f0;
            padding-top: 12px;
        }
        .file-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
            flex-wrap: wrap;
            gap: 10px;
        }
        .file-name {
            font-family: monospace;
            font-size: 13px;
            word-break: break-all;
            flex: 1;
        }
        .file-size {
            font-size: 12px;
            color: #718096;
            white-space: nowrap;
        }
        .models-table {
            width: 100%;
            border-collapse: collapse;
        }
        .models-table th, .models-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }
        .models-table th {
            background: #f7fafc;
            font-weight: 600;
        }
        .progress-bar {
            background: #e2e8f0;
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            width: 0%;
            height: 20px;
            background: #667eea;
            transition: width 0.3s;
        }
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
        .info-text {
            font-size: 12px;
            color: #718096;
            margin-top: 10px;
            padding: 10px;
            background: #f7fafc;
            border-radius: 8px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid #e2e8f0;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background: none;
            color: #718096;
        }
        .tab.active {
            color: #667eea;
            border-bottom: 2px solid #667eea;
            border-radius: 0;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .downloads-count {
            font-weight: bold;
            color: #667eea;
        }
        code {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>📦 模型管理</h1>
            <p class="subtitle">搜索、下载和管理 GGUF 模型</p>
            
            <div class="tabs">
                <button class="tab active" onclick="switchTab('download')">📥 下载模型</button>
                <button class="tab" onclick="switchTab('local')">💾 本地模型</button>
                <button class="tab" onclick="switchTab('settings')">⚙️ 设置</button>
            </div>
            
            <!-- 下载模型标签页 -->
            <div id="tab-download" class="tab-content active">
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="搜索 GGUF 模型... (例如: llama, qwen, mistral)">
                    <button onclick="searchModels()" id="searchBtn">🔍 搜索</button>
                    <button onclick="clearSearch()">🗑️ 清空</button>
                </div>
                <div class="info-text" style="margin-bottom: 10px;">
                    💡 提示：搜索会自动添加 "GGUF" 关键词，只显示可下载的量化模型。
                </div>
                <div id="searchResults"></div>
            </div>
            
            <!-- 本地模型标签页 -->
            <div id="tab-local" class="tab-content">
                <div style="margin-bottom: 15px; display: flex; gap: 10px;">
                    <button onclick="refreshLocalModels()">🔄 刷新列表</button>
                    <button onclick="createSymlinks()">🔗 创建软链接</button>
                </div>
                <div id="localModelsList">
                    <div class="loading"></div> 加载中...
                </div>
            </div>
            
            <!-- 设置标签页 -->
            <div id="tab-settings" class="tab-content">
                <h3>📁 模型存储路径</h3>
                <div class="info-text">
                    <strong>模型目录:</strong> /opt/llamapanel/models/<br>
                    <strong>软链接目录:</strong> /opt/llamapanel/model_links/ (独立目录，不受 llama.cpp 更新影响)<br><br>
                    <strong>✨ 特性说明:</strong><br>
                    • 模型文件直接下载到模型目录，无需临时目录<br>
                    • 下载完成后自动创建软链接到独立目录<br>
                    • <span style="color: #e53e3e;">删除或更新 llama.cpp 目录不会影响已下载的模型和软链接</span><br><br>
                    <strong>💡 使用提示:</strong><br>
                    如需在 llama.cpp 中使用模型，请使用软链接目录中的文件路径：<br>
                    <code>/opt/llamapanel/model_links/模型文件名.gguf</code>
                </div>
            </div>
        </div>
        
        <!-- 下载进度 -->
        <div id="downloadProgress" class="card" style="display: none;">
            <h2>📥 下载进度</h2>
            <div class="progress-bar">
                <div id="progressFill" class="progress-fill"></div>
            </div>
            <div id="progressText" style="font-size: 14px;">准备下载...</div>
        </div>
    </div>
    
    <script>
        let currentSearchResults = [];
        let filesCache = {};  // 内存缓存已加载的文件列表
        
        // ========== 缓存持久化到 sessionStorage ==========
        
        // 保存文件列表缓存到 sessionStorage
        function saveFilesCacheToSession() {
            try {
                sessionStorage.setItem('filesCache', JSON.stringify(filesCache));
            } catch(e) {
                console.error('保存缓存失败:', e);
            }
        }
        
        // 从 sessionStorage 恢复文件列表缓存
        function restoreFilesCacheFromSession() {
            try {
                const savedCache = sessionStorage.getItem('filesCache');
                if (savedCache) {
                    filesCache = JSON.parse(savedCache);
                    console.log('恢复了', Object.keys(filesCache).length, '个文件列表缓存');
                }
            } catch(e) {
                console.error('恢复缓存失败:', e);
            }
        }
        
        // 保存搜索状态到 sessionStorage
        function saveSearchState(query, resultsHtml) {
            if (query) {
                sessionStorage.setItem('lastSearchQuery', query);
                sessionStorage.setItem('lastSearchResultsHtml', resultsHtml);
                sessionStorage.setItem('lastSearchTime', Date.now());
            }
        }
        
        // 恢复上次搜索状态
        function restoreSearchState() {
            const savedQuery = sessionStorage.getItem('lastSearchQuery');
            const savedResultsHtml = sessionStorage.getItem('lastSearchResultsHtml');
            const savedTime = sessionStorage.getItem('lastSearchTime');
            
            if (savedQuery && savedResultsHtml && savedTime && (Date.now() - parseInt(savedTime)) < 600000) {
                document.getElementById('searchInput').value = savedQuery;
                const resultsDiv = document.getElementById('searchResults');
                if (resultsDiv && savedResultsHtml && savedResultsHtml !== '') {
                    resultsDiv.innerHTML = savedResultsHtml;
                    rebindToggleEvents();
                    return true;
                }
            }
            return false;
        }
        
        // 保存模型文件的展开状态到 sessionStorage
        function saveModelFilesState(modelId, isExpanded) {
            const states = JSON.parse(sessionStorage.getItem('modelFilesExpanded') || '{}');
            states[modelId] = isExpanded;
            sessionStorage.setItem('modelFilesExpanded', JSON.stringify(states));
        }
        
        // 恢复所有模型文件的展开状态
        function restoreModelFilesStates() {
            const states = JSON.parse(sessionStorage.getItem('modelFilesExpanded') || '{}');
            for (const [modelId, isExpanded] of Object.entries(states)) {
                if (isExpanded) {
                    setTimeout(() => {
                        const safeId = modelId.replace(/[^a-zA-Z0-9]/g, '_');
                        const container = document.getElementById(`files-${safeId}`);
                        if (container && container.style.display !== 'block') {
                            // 优先使用 session 缓存
                            if (filesCache[modelId]) {
                                container.innerHTML = filesCache[modelId];
                                container.style.display = 'block';
                            } else {
                                getModelFiles(modelId, true);
                            }
                        }
                    }, 150);
                }
            }
        }
        
        // 重新绑定折叠事件
        function rebindToggleEvents() {
            document.querySelectorAll('.model-name').forEach(el => {
                const card = el.closest('.model-card');
                if (card) {
                    const filesDiv = card.querySelector('[id^="files-"]');
                    const btn = card.querySelector('button[id^="btn-"]');
                    if (filesDiv && btn) {
                        const modelId = btn.getAttribute('data-model-id');
                        el.onclick = function() {
                            if (filesDiv.style.display === 'none' || filesDiv.style.display === '') {
                                if (filesDiv.innerHTML.trim() === '' || filesDiv.innerHTML.includes('该模型没有') || filesDiv.innerHTML.includes('获取文件列表失败')) {
                                    if (modelId) getModelFiles(modelId);
                                } else {
                                    filesDiv.style.display = 'block';
                                    if (modelId) saveModelFilesState(modelId, true);
                                }
                            } else {
                                filesDiv.style.display = 'none';
                                if (modelId) saveModelFilesState(modelId, false);
                            }
                        };
                    }
                }
            });
        }
        
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            
            if (tabName === 'download') {
                document.querySelector('.tab:first-child').classList.add('active');
                document.getElementById('tab-download').classList.add('active');
            } else if (tabName === 'local') {
                document.querySelectorAll('.tab')[1].classList.add('active');
                document.getElementById('tab-local').classList.add('active');
                refreshLocalModels();
            } else if (tabName === 'settings') {
                document.querySelectorAll('.tab')[2].classList.add('active');
                document.getElementById('tab-settings').classList.add('active');
            }
        }
        
        function formatDownloads(downloads) {
            if (downloads >= 1000000) {
                return (downloads / 1000000).toFixed(1) + 'M';
            } else if (downloads >= 1000) {
                return (downloads / 1000).toFixed(0) + 'K';
            }
            return downloads.toString();
        }
        
        function toggleModelFiles(safeId) {
            const container = document.getElementById(`files-${safeId}`);
            if (container) {
                if (container.style.display === 'none' || container.style.display === '') {
                    container.style.display = 'block';
                } else {
                    container.style.display = 'none';
                }
            }
        }
        
        async function searchModels() {
            const query = document.getElementById('searchInput').value.trim();
            console.log('搜索关键词:', query);
            
            if (!query) {
                alert('请输入搜索关键词');
                return;
            }
            
            const btn = document.getElementById('searchBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> 搜索中...';
            
            try {
                const response = await fetch(`/models/api/search?q=${encodeURIComponent(query)}&limit=30`);
                const data = await response.json();
                console.log('API返回数据:', data);
                
                const resultsDiv = document.getElementById('searchResults');
                
                if (data.success && data.results && data.results.length > 0) {
                    currentSearchResults = data.results;
                    let html = '';
                    for (const model of data.results) {
                        const safeId = model.id.replace(/[^a-zA-Z0-9]/g, '_');
                        const downloadsFormatted = formatDownloads(model.downloads);
                        html += `
                            <div class="model-card" id="card-${safeId}">
                                <div class="model-name" onclick="toggleModelFiles('${safeId}')">
                                    📄 ${model.name}
                                </div>
                                <div class="model-meta">
                                    作者: ${model.author} | ❤️ ${model.likes} | 📥 <span class="downloads-count">${downloadsFormatted}</span>
                                </div>
                                <button onclick="getModelFiles('${model.id.replace(/'/g, "\\'")}')" id="btn-${safeId}" data-model-id="${model.id}">📂 查看 GGUF 文件</button>
                                <div id="files-${safeId}" style="margin-top: 12px; display: none;"></div>
                            </div>
                        `;
                    }
                    resultsDiv.innerHTML = html;
                    saveSearchState(query, html);
                } else {
                    resultsDiv.innerHTML = '<div class="info-text">❌ 未找到相关 GGUF 模型</div>';
                    saveSearchState(query, '');
                }
            } catch(e) {
                console.error('搜索失败:', e);
                document.getElementById('searchResults').innerHTML = '<div class="info-text">❌ 搜索失败: ' + e.message + '</div>';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🔍 搜索';
            }
        }
        
        function clearSearch() {
            document.getElementById('searchInput').value = '';
            document.getElementById('searchResults').innerHTML = '';
            currentSearchResults = [];
            // 清空内存缓存和 session 缓存
            filesCache = {};
            sessionStorage.removeItem('filesCache');
            sessionStorage.removeItem('lastSearchQuery');
            sessionStorage.removeItem('lastSearchResultsHtml');
            sessionStorage.removeItem('lastSearchTime');
            sessionStorage.removeItem('modelFilesExpanded');
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function getModelFiles(modelId, silent = false) {
            const safeId = modelId.replace(/[^a-zA-Z0-9]/g, '_');
            const btn = document.getElementById(`btn-${safeId}`);
            const container = document.getElementById(`files-${safeId}`);
            
            if (!btn || !container) return;
            
            // 如果已经展开，则收拢
            if (container.style.display === 'block') {
                container.style.display = 'none';
                if (!silent) saveModelFilesState(modelId, false);
                return;
            }
            
            // 检查内存缓存
            if (filesCache[modelId]) {
                container.innerHTML = filesCache[modelId];
                container.style.display = 'block';
                if (!silent) saveModelFilesState(modelId, true);
                return;
            }
            
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> 加载中...';
            
            try {
                const response = await fetch(`/models/api/files?model_id=${encodeURIComponent(modelId)}`);
                const data = await response.json();
                
                let html = '';
                if (data.success && data.files && data.files.length > 0) {
                    html = '<div class="file-list"><strong>📁 GGUF 文件列表:</strong>';
                    for (const file of data.files) {
                        html += `
                            <div class="file-item">
                                <span class="file-name">${escapeHtml(file.filename)}</span>
                                <span class="file-size">${file.size_str}</span>
                                <button class="small" onclick="downloadModel('${file.download_url}', '${file.filename}')">⬇️ 下载</button>
                            </div>
                        `;
                    }
                    html += '</div>';
                } else {
                    html = '<div class="info-text">⚠️ 该模型没有 GGUF 文件</div>';
                }
                
                // 存入内存缓存和 session 缓存
                filesCache[modelId] = html;
                saveFilesCacheToSession();
                
                container.innerHTML = html;
                container.style.display = 'block';
                if (!silent) saveModelFilesState(modelId, true);
            } catch(e) {
                console.error('获取文件失败:', e);
                const errorHtml = '<div class="info-text">❌ 获取文件列表失败: ' + e.message + '</div>';
                filesCache[modelId] = errorHtml;
                saveFilesCacheToSession();
                container.innerHTML = errorHtml;
                container.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '📂 查看 GGUF 文件';
            }
        }
        
        async function downloadModel(downloadUrl, filename) {
            if (confirm(`下载 ${filename}？\\n文件可能较大，请耐心等待。`)) {
                const progressDiv = document.getElementById('downloadProgress');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                progressDiv.style.display = 'block';
                progressFill.style.width = '0%';
                progressText.innerText = '开始下载...';
                
                try {
                    const response = await fetch('/models/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ download_url: downloadUrl, filename: filename })
                    });
                    const result = await response.json();
                    alert(result.message);
                    startPollingProgress(filename);
                } catch(e) {
                    console.error('下载失败:', e);
                    alert('下载失败: ' + e.message);
                    progressDiv.style.display = 'none';
                }
            }
        }
        
        async function refreshLocalModels() {
            const modelsDiv = document.getElementById('localModelsList');
            modelsDiv.innerHTML = '<div class="loading"></div> 加载中...';
            
            try {
                const response = await fetch('/models/api/local');
                const data = await response.json();
                
                if (data.success && data.models && data.models.length > 0) {
                    let html = '<table class="models-table">';
                    html += '<thead><tr><th>模型名称</th><th>大小</th><th>修改时间</th><th>操作</th></tr></thead><tbody>';
                    for (const model of data.models) {
                        html += `
                            <tr>
                                <td>${escapeHtml(model.name)}</td>
                                <td>${model.size_str}</td>
                                <td>${model.modified}</td>
                                <td><button class="small" onclick="deleteModel('${escapeHtml(model.name)}')">🗑️ 删除</button></td>
                            </tr>
                        `;
                    }
                    html += '</tbody></table>';
                    modelsDiv.innerHTML = html;
                } else {
                    modelsDiv.innerHTML = '<div class="info-text">暂无本地模型，请从「下载模型」页面下载</div>';
                }
            } catch(e) {
                console.error('刷新失败:', e);
                modelsDiv.innerHTML = '<div class="info-text">加载失败: ' + e.message + '</div>';
            }
        }
        
        async function deleteModel(filename) {
            if (confirm(`确定删除 ${filename}？`)) {
                try {
                    const response = await fetch(`/models/api/delete?filename=${encodeURIComponent(filename)}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    alert(data.message);
                    refreshLocalModels();
                } catch(e) {
                    console.error('删除失败:', e);
                    alert('删除失败: ' + e.message);
                }
            }
        }
        
        async function createSymlinks() {
            try {
                const response = await fetch('/models/api/symlinks', { method: 'POST' });
                const data = await response.json();
                alert(data.message);
                refreshLocalModels();
            } catch(e) {
                console.error('创建软链接失败:', e);
                alert('创建失败: ' + e.message);
            }
        }
        
        let progressInterval = null;
        
        function startPollingProgress(filename) {
            if (progressInterval) clearInterval(progressInterval);
            progressInterval = setInterval(() => {
                checkDownloadStatus(filename);
            }, 2000);
            setTimeout(() => {
                if (progressInterval) {
                    clearInterval(progressInterval);
                    progressInterval = null;
                    document.getElementById('downloadProgress').style.display = 'none';
                }
            }, 60000);
        }
        
        async function checkDownloadStatus(filename) {
            try {
                const response = await fetch('/models/api/local');
                const data = await response.json();
                if (data.success && data.models) {
                    const found = data.models.find(m => m.name === filename);
                    if (found) {
                        document.getElementById('progressFill').style.width = '100%';
                        document.getElementById('progressText').innerText = '下载完成！';
                        setTimeout(() => {
                            document.getElementById('downloadProgress').style.display = 'none';
                            if (progressInterval) clearInterval(progressInterval);
                            refreshLocalModels();
                        }, 2000);
                    }
                }
            } catch(e) {
                console.error('检查状态失败:', e);
            }
        }
        
        // 页面加载时恢复所有状态
        document.addEventListener('DOMContentLoaded', function() {
            restoreFilesCacheFromSession();  // 先恢复缓存
            restoreSearchState();            // 恢复搜索状态
            refreshLocalModels();            // 刷新本地模型
            setTimeout(() => {
                restoreModelFilesStates();    // 恢复展开状态
            }, 300);
        });
    </script>
</body>
</html>
'''

@router.get("")
async def models_page():
    """模型管理页面"""
    return HTMLResponse(content=MODELS_PAGE)

@router.get("/api/search")
async def search_models(q: str, limit: int = 30):
    """搜索 HuggingFace 模型"""
    results = model_manager.search_huggingface_models(q, limit)
    return {"success": True, "results": results}

@router.get("/api/files")
async def get_model_files(model_id: str):
    """获取模型的 GGUF 文件列表"""
    files = model_manager.get_model_files(model_id)
    return {"success": True, "files": files}

@router.post("/api/download")
async def download_model(request: Request, background_tasks: BackgroundTasks):
    """下载模型（后台任务）"""
    data = await request.json()
    download_url = data.get('download_url')
    filename = data.get('filename')
    
    if not download_url or not filename:
        return {"success": False, "message": "缺少必要参数"}
    
    def run_download():
        model_manager.download_model(download_url, filename)
    
    background_tasks.add_task(run_download)
    return {"success": True, "message": f"开始下载 {filename}"}

@router.get("/api/local")
async def get_local_models():
    """获取本地已下载的模型列表"""
    models = model_manager.get_local_models()
    return {"success": True, "models": models}

@router.delete("/api/delete")
async def delete_model(filename: str):
    """删除本地模型"""
    success = model_manager.delete_model(filename)
    if success:
        return {"success": True, "message": f"已删除 {filename}"}
    else:
        return {"success": False, "message": "删除失败"}

@router.post("/api/symlinks")
async def create_symlinks():
    """创建所有模型的软链接"""
    count = model_manager.create_symlinks()
    return {"success": True, "message": f"已创建 {count} 个软链接"}