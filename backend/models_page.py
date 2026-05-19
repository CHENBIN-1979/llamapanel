#!/usr/bin/env python3
import time
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
        button.small { padding: 4px 12px; font-size: 12px; min-width: 75px; }
        button.tiny { padding: 4px 8px; font-size: 11px; min-width: 36px; }
        button:disabled { opacity: 0.7; cursor: not-allowed; transform: none; }
        .download-btn {
            background: #667eea;
        }
        .download-btn.downloading {
            background: #38a169;
        }
        .download-btn.downloaded {
            background: #38a169;
            cursor: default;
        }
        .download-btn.downloaded:hover {
            transform: none;
            background: #38a169;
        }
        .control-btn {
            background: #4a5568;
        }
        .control-btn:hover {
            background: #2d3748;
            transform: none;
        }
        .control-btn.stop {
            background: #e53e3e;
        }
        .control-btn.stop:hover {
            background: #c53030;
        }
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
            gap: 8px;
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
        .button-group {
            display: flex;
            gap: 5px;
            align-items: center;
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
                    • mmproj 文件自动存储到模型专属子目录，避免冲突<br>
                    • 支持暂停/继续下载（断点续传）<br>
                    • <span style="color: #e53e3e;">删除或更新 llama.cpp 目录不会影响已下载的模型和软链接</span><br><br>
                    <strong>💡 使用提示:</strong><br>
                    如需在 llama.cpp 中使用模型，请使用软链接目录中的文件路径：<br>
                    <code>/opt/llamapanel/model_links/模型文件名.gguf</code><br>
                    <code>/opt/llamapanel/model_links/模型文件夹/mmproj文件.gguf</code>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentSearchResults = [];
        let filesCache = {};
        let progressIntervals = {};
        let downloadingFiles = {};
        let expandedModels = {};
        
        // 存储每个文件的下载URL和modelId
        let fileDownloadUrls = {};
        let fileModelIdMap = {};
        
        function saveFilesCacheToSession() {
            try {
                sessionStorage.setItem('filesCache', JSON.stringify(filesCache));
                sessionStorage.setItem('expandedModels', JSON.stringify(expandedModels));
                sessionStorage.setItem('fileDownloadUrls', JSON.stringify(fileDownloadUrls));
                sessionStorage.setItem('fileModelIdMap', JSON.stringify(fileModelIdMap));
            } catch(e) {
                console.error('保存缓存失败:', e);
            }
        }
        
        function restoreFilesCacheFromSession() {
            try {
                const savedCache = sessionStorage.getItem('filesCache');
                if (savedCache) {
                    filesCache = JSON.parse(savedCache);
                }
                const savedExpanded = sessionStorage.getItem('expandedModels');
                if (savedExpanded) {
                    expandedModels = JSON.parse(savedExpanded);
                }
                const savedUrls = sessionStorage.getItem('fileDownloadUrls');
                if (savedUrls) {
                    fileDownloadUrls = JSON.parse(savedUrls);
                }
                const savedMap = sessionStorage.getItem('fileModelIdMap');
                if (savedMap) {
                    fileModelIdMap = JSON.parse(savedMap);
                }
            } catch(e) {
                console.error('恢复缓存失败:', e);
            }
        }
        
        function saveSearchState(query, resultsHtml) {
            if (query) {
                sessionStorage.setItem('lastSearchQuery', query);
                sessionStorage.setItem('lastSearchResultsHtml', resultsHtml);
                sessionStorage.setItem('lastSearchTime', Date.now());
            }
        }
        
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
                    restoreExpandedStates();
                    restoreDownloadingStates();
                    return true;
                }
            }
            return false;
        }
        
        function restoreExpandedStates() {
            for (const [modelId, isExpanded] of Object.entries(expandedModels)) {
                if (isExpanded) {
                    const safeId = modelId.replace(/[^a-zA-Z0-9]/g, '_');
                    const container = document.getElementById(`files-${safeId}`);
                    if (container && container.style.display !== 'block') {
                        if (filesCache[modelId]) {
                            container.innerHTML = filesCache[modelId];
                            container.style.display = 'block';
                            restoreDownloadingStates();
                        } else {
                            loadModelFiles(modelId, true);
                        }
                    }
                }
            }
        }
        
        function restoreDownloadingStates() {
            for (const [filename, progress] of Object.entries(downloadingFiles)) {
                if (progress !== undefined && progress < 100) {
                    const ctrlGroup = document.getElementById(getControlGroupId(filename));
                    if (ctrlGroup && ctrlGroup.innerHTML.indexOf('下载') !== -1) {
                        const downloadUrl = fileDownloadUrls[filename] || '';
                        const modelId = fileModelIdMap[filename] || '';
                        if (downloadUrl) {
                            ctrlGroup.innerHTML = `
                                <button id="${getButtonId(filename)}" class="small download-btn downloading" style="background:#38a169;" disabled>${progress}%</button>
                                <button class="tiny control-btn" onclick="pauseDownload('${escapeHtml(filename)}')">⏸</button>
                                <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(filename)}', '${modelId}')">🗑</button>
                            `;
                        }
                    }
                }
            }
        }
        
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
                                    if (modelId) loadModelFiles(modelId);
                                } else {
                                    filesDiv.style.display = 'block';
                                    expandedModels[modelId] = true;
                                    saveFilesCacheToSession();
                                    restoreDownloadingStates();
                                }
                            } else {
                                filesDiv.style.display = 'none';
                                expandedModels[modelId] = false;
                                saveFilesCacheToSession();
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
                setTimeout(() => {
                    restoreExpandedStates();
                }, 100);
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
                                <button onclick="loadModelFiles('${model.id.replace(/'/g, "\\'")}')" id="btn-${safeId}" data-model-id="${model.id}">📂 查看 GGUF 文件</button>
                                <div id="files-${safeId}" style="margin-top: 12px; display: none;"></div>
                            </div>
                        `;
                    }
                    resultsDiv.innerHTML = html;
                    saveSearchState(query, html);
                    restoreExpandedStates();
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
            filesCache = {};
            expandedModels = {};
            fileDownloadUrls = {};
            fileModelIdMap = {};
            sessionStorage.removeItem('filesCache');
            sessionStorage.removeItem('expandedModels');
            sessionStorage.removeItem('fileDownloadUrls');
            sessionStorage.removeItem('fileModelIdMap');
            sessionStorage.removeItem('lastSearchQuery');
            sessionStorage.removeItem('lastSearchResultsHtml');
            sessionStorage.removeItem('lastSearchTime');
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function getButtonId(filename) {
            return 'btn-download-' + filename.replace(/[^a-zA-Z0-9]/g, '_');
        }
        
        function getControlGroupId(filename) {
            return 'ctrl-group-' + filename.replace(/[^a-zA-Z0-9]/g, '_');
        }
        
        // 刷新指定模型的文件列表（不改变展开状态）
        async function refreshModelFiles(modelId) {
            const safeId = modelId.replace(/[^a-zA-Z0-9]/g, '_');
            const container = document.getElementById(`files-${safeId}`);
            if (container && container.style.display === 'block') {
                delete filesCache[modelId];
                await loadModelFiles(modelId, true);
            }
        }
        
        async function loadModelFiles(modelId, silent = false) {
            const safeId = modelId.replace(/[^a-zA-Z0-9]/g, '_');
            const btn = document.getElementById(`btn-${safeId}`);
            const container = document.getElementById(`files-${safeId}`);
            
            if (!btn || !container) return;
            
            if (container.style.display === 'block') {
                container.style.display = 'none';
                expandedModels[modelId] = false;
                saveFilesCacheToSession();
                return;
            }
            
            if (filesCache[modelId]) {
                container.innerHTML = filesCache[modelId];
                container.style.display = 'block';
                expandedModels[modelId] = true;
                saveFilesCacheToSession();
                restoreDownloadingStates();
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
                        const isDownloaded = file.is_downloaded === true;
                        const hasPartial = file.has_partial === true;
                        const buttonId = getButtonId(file.filename);
                        const ctrlGroupId = getControlGroupId(file.filename);
                        
                        fileDownloadUrls[file.filename] = file.download_url;
                        fileModelIdMap[file.filename] = modelId;
                        
                        let buttonHtml = '';
                        if (isDownloaded) {
                            buttonHtml = `
                                <div class="button-group" id="${ctrlGroupId}">
                                    <button id="${buttonId}" class="small download-btn downloaded" disabled style="background:#38a169;">✅ 已下载</button>
                                </div>
                            `;
                        } else if (downloadingFiles[file.filename] !== undefined && downloadingFiles[file.filename] < 100) {
                            const progress = downloadingFiles[file.filename];
                            buttonHtml = `
                                <div class="button-group" id="${ctrlGroupId}">
                                    <button id="${buttonId}" class="small download-btn downloading" style="background:#38a169;" disabled>${progress}%</button>
                                    <button class="tiny control-btn" onclick="pauseDownload('${escapeHtml(file.filename)}')">⏸</button>
                                    <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(file.filename)}', '${modelId}')">🗑</button>
                                </div>
                            `;
                        } else if (hasPartial) {
                            // 有部分下载的文件，显示百分比进度
                            let partialPercent = 0;
                            if (downloadingFiles[file.filename] !== undefined && downloadingFiles[file.filename] > 0) {
                                partialPercent = downloadingFiles[file.filename];
                            }
                            let displayText = partialPercent > 0 ? `${partialPercent}%` : '▶ 继续';
                            buttonHtml = `
                                <div class="button-group" id="${ctrlGroupId}">
                                    <button id="${buttonId}" class="small download-btn" onclick="resumeDownload('${file.download_url}', '${escapeHtml(file.filename)}', '${modelId}')">${displayText}</button>
                                    <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(file.filename)}', '${modelId}')">🗑</button>
                                </div>
                            `;
                        } else {
                            buttonHtml = `
                                <div class="button-group" id="${ctrlGroupId}">
                                    <button id="${buttonId}" class="small download-btn" onclick="downloadModel('${file.download_url}', '${escapeHtml(file.filename)}', '${modelId}')">⬇️ 下载</button>
                                </div>
                            `;
                        }
                        
                        html += `
                            <div class="file-item" data-filename="${escapeHtml(file.filename)}">
                                <span class="file-name">${escapeHtml(file.filename)}</span>
                                <span class="file-size">${file.size_str}</span>
                                ${buttonHtml}
                            </div>
                        `;
                    }
                    html += '</div>';
                } else {
                    html = '<div class="info-text">⚠️ 该模型没有 GGUF 文件</div>';
                }
                
                filesCache[modelId] = html;
                container.innerHTML = html;
                container.style.display = 'block';
                expandedModels[modelId] = true;
                saveFilesCacheToSession();
                restoreDownloadingStates();
            } catch(e) {
                console.error('获取文件失败:', e);
                const errorHtml = '<div class="info-text">❌ 获取文件列表失败: ' + e.message + '</div>';
                filesCache[modelId] = errorHtml;
                container.innerHTML = errorHtml;
                container.style.display = 'block';
            } finally {
                btn.disabled = false;
                btn.innerHTML = '📂 查看 GGUF 文件';
            }
        }
        
        async function getDownloadProgress(filename) {
            try {
                const response = await fetch(`/models/api/progress?filename=${encodeURIComponent(filename)}`);
                const data = await response.json();
                return data;
            } catch(e) {
                console.error('获取进度失败:', e);
                return null;
            }
        }
        
        function updateDownloadButton(filename, percent, status) {
            const buttonId = getButtonId(filename);
            const ctrlGroupId = getControlGroupId(filename);
            const ctrlGroup = document.getElementById(ctrlGroupId);
            
            if (status === 'completed') {
                if (ctrlGroup) {
                    ctrlGroup.innerHTML = `<button id="${buttonId}" class="small download-btn downloaded" disabled style="background:#38a169;">✅ 已下载</button>`;
                }
                delete downloadingFiles[filename];
                if (progressIntervals[filename]) {
                    clearInterval(progressIntervals[filename]);
                    delete progressIntervals[filename];
                }
                refreshLocalModels();
                for (const modelId in expandedModels) {
                    if (expandedModels[modelId]) {
                        refreshModelFiles(modelId);
                    }
                }
            } else if (status === 'downloading') {
                if (ctrlGroup) {
                    if (ctrlGroup.innerHTML.indexOf('⏸') === -1) {
                        const downloadUrl = fileDownloadUrls[filename] || '';
                        const modelId = fileModelIdMap[filename] || '';
                        ctrlGroup.innerHTML = `
                            <button id="${buttonId}" class="small download-btn downloading" style="background:#38a169;" disabled>${percent}%</button>
                            <button class="tiny control-btn" onclick="pauseDownload('${escapeHtml(filename)}')">⏸</button>
                            <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(filename)}', '${modelId}')">🗑</button>
                        `;
                    } else {
                        const percentBtn = ctrlGroup.querySelector(`#${buttonId}`);
                        if (percentBtn) {
                            percentBtn.innerHTML = percent + '%';
                        }
                    }
                }
                downloadingFiles[filename] = percent;
            } else if (status === 'paused') {
                if (ctrlGroup) {
                    const downloadUrl = fileDownloadUrls[filename] || '';
                    const modelId = fileModelIdMap[filename] || '';
                    const displayPercent = percent > 0 ? `${percent}%` : '▶ 继续';
                    ctrlGroup.innerHTML = `
                        <button id="${buttonId}" class="small download-btn" onclick="resumeDownload('${downloadUrl}', '${escapeHtml(filename)}', '${modelId}')">${displayPercent}</button>
                        <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(filename)}', '${modelId}')">🗑</button>
                    `;
                }
                delete downloadingFiles[filename];
                if (progressIntervals[filename]) {
                    clearInterval(progressIntervals[filename]);
                    delete progressIntervals[filename];
                }
            } else if (status === 'stopped') {
                if (ctrlGroup) {
                    const downloadUrl = fileDownloadUrls[filename] || '';
                    const modelId = fileModelIdMap[filename] || '';
                    ctrlGroup.innerHTML = `<button id="${buttonId}" class="small download-btn" onclick="downloadModel('${downloadUrl}', '${escapeHtml(filename)}', '${modelId}')">⬇️ 下载</button>`;
                }
                delete downloadingFiles[filename];
                if (progressIntervals[filename]) {
                    clearInterval(progressIntervals[filename]);
                    delete progressIntervals[filename];
                }
            }
        }
        
        function startProgressPolling(filename) {
            if (progressIntervals[filename]) {
                clearInterval(progressIntervals[filename]);
            }
            
            progressIntervals[filename] = setInterval(async () => {
                try {
                    const progress = await getDownloadProgress(filename);
                    
                    if (progress && progress.downloading === true) {
                        let percent = progress.percent;
                        if (percent < 0) percent = 0;
                        if (percent > 100) percent = 100;
                        updateDownloadButton(filename, percent, 'downloading');
                        
                        if (percent >= 100) {
                            updateDownloadButton(filename, 100, 'completed');
                        }
                    } else if (progress && progress.downloading === false && progress.percent === 100) {
                        updateDownloadButton(filename, 100, 'completed');
                    } else if (progress && progress.percent === -1) {
                        updateDownloadButton(filename, 0, 'failed');
                    }
                } catch(e) {
                    console.error('轮询进度出错:', e);
                }
            }, 1000);
        }
        
        async function downloadModel(downloadUrl, filename, modelId) {
            if (confirm(`下载 ${filename}？\\n文件可能较大，请耐心等待。`)) {
                const ctrlGroupId = getControlGroupId(filename);
                const ctrlGroup = document.getElementById(ctrlGroupId);
                if (ctrlGroup) {
                    ctrlGroup.innerHTML = `
                        <button id="${getButtonId(filename)}" class="small download-btn downloading" style="background:#38a169;" disabled>0%</button>
                        <button class="tiny control-btn" onclick="pauseDownload('${escapeHtml(filename)}')">⏸</button>
                        <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(filename)}', '${modelId}')">🗑</button>
                    `;
                }
                downloadingFiles[filename] = 0;
                
                try {
                    const response = await fetch('/models/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ download_url: downloadUrl, filename: filename, model_id: modelId })
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        startProgressPolling(filename);
                    } else {
                        alert('启动下载失败: ' + result.message);
                        updateDownloadButton(filename, 0, 'stopped');
                    }
                } catch(e) {
                    console.error('下载失败:', e);
                    alert('下载失败: ' + e.message);
                    updateDownloadButton(filename, 0, 'stopped');
                }
            }
        }
        
        async function pauseDownload(filename) {
            try {
                const response = await fetch('/models/api/pause', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename: filename })
                });
                const result = await response.json();
                if (result.success) {
                    updateDownloadButton(filename, 0, 'paused');
                } else {
                    alert('暂停失败: ' + result.message);
                }
            } catch(e) {
                console.error('暂停失败:', e);
                alert('暂停失败: ' + e.message);
            }
        }
        
        async function deletePartial(filename, modelId) {
            if (confirm(`删除 ${filename} 的部分下载文件？`)) {
                try {
                    const response = await fetch('/models/api/delete_partial', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ filename: filename, model_id: modelId })
                    });
                    const result = await response.json();
                    if (result.success) {
                        updateDownloadButton(filename, 0, 'stopped');
                        for (const cacheModelId in expandedModels) {
                            if (expandedModels[cacheModelId]) {
                                delete filesCache[cacheModelId];
                                await loadModelFiles(cacheModelId, true);
                                break;
                            }
                        }
                        refreshLocalModels();
                    } else {
                        alert('删除失败: ' + result.message);
                    }
                } catch(e) {
                    console.error('删除失败:', e);
                    alert('删除失败: ' + e.message);
                }
            }
        }
        
        async function resumeDownload(downloadUrl, filename, modelId) {
            // 先获取已有的进度
            let existingPercent = 0;
            try {
                const progressResponse = await fetch(`/models/api/progress?filename=${encodeURIComponent(filename)}`);
                const existingProgress = await progressResponse.json();
                if (existingProgress && existingProgress.percent > 0 && existingProgress.percent < 100) {
                    existingPercent = existingProgress.percent;
                }
            } catch(e) {
                console.log('获取已有进度失败:', e);
            }
            
            const ctrlGroupId = getControlGroupId(filename);
            const ctrlGroup = document.getElementById(ctrlGroupId);
            if (ctrlGroup) {
                ctrlGroup.innerHTML = `
                    <button id="${getButtonId(filename)}" class="small download-btn downloading" style="background:#38a169;" disabled>${existingPercent > 0 ? existingPercent + '%' : '0%'}</button>
                    <button class="tiny control-btn" onclick="pauseDownload('${escapeHtml(filename)}')">⏸</button>
                    <button class="tiny control-btn stop" onclick="deletePartial('${escapeHtml(filename)}', '${modelId}')">🗑</button>
                `;
            }
            downloadingFiles[filename] = existingPercent;
            
            try {
                const response = await fetch('/models/api/resume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ download_url: downloadUrl, filename: filename, model_id: modelId })
                });
                const result = await response.json();
                if (result.success) {
                    startProgressPolling(filename);
                } else {
                    alert('恢复失败: ' + result.message);
                    updateDownloadButton(filename, 0, 'stopped');
                }
            } catch(e) {
                console.error('恢复失败:', e);
                alert('恢复失败: ' + e.message);
                updateDownloadButton(filename, 0, 'stopped');
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
                    html += '<thead><tr><th>模型名称</th><th>大小</th><th>修改时间</th><th>操作</th></table></thead><tbody>';
                    for (const model of data.models) {
                        let displayName = model.name;
                        let isPartial = displayName.endsWith('.partial') || displayName.includes('.partial');
                        let sizeClass = isPartial ? 'style="color: #e67e22;"' : '';
                        html += `
                            <tr>
                                <td>${sizeClass}${escapeHtml(displayName)}${isPartial ? ' (下载中)' : ''}${sizeClass ? '</span>' : ''}</td>
                                <td>${model.size_str}</td>
                                <td>${model.modified}</td>
                                <td><button class="small danger" onclick="deleteLocalModel('${escapeHtml(model.name)}')">🗑️ 删除</button></td>
                            </tr>
                        `;
                    }
                    html += '</tbody></tr>';
                    modelsDiv.innerHTML = html;
                } else {
                    modelsDiv.innerHTML = '<div class="info-text">暂无本地模型，请从「下载模型」页面下载</div>';
                }
            } catch(e) {
                console.error('刷新失败:', e);
                modelsDiv.innerHTML = '<div class="info-text">加载失败: ' + e.message + '</div>';
            }
        }
        
        async function deleteLocalModel(filename) {
            if (confirm(`确定删除 ${filename}？`)) {
                try {
                    const response = await fetch(`/models/api/delete?filename=${encodeURIComponent(filename)}`, {
                        method: 'DELETE'
                    });
                    const data = await response.json();
                    alert(data.message);
                    refreshLocalModels();
                    
                    const baseFilename = filename.split('/').pop().replace('.partial', '');
                    
                    for (const cacheModelId in filesCache) {
                        if (filesCache[cacheModelId].includes(escapeHtml(baseFilename))) {
                            delete filesCache[cacheModelId];
                            if (expandedModels[cacheModelId]) {
                                await loadModelFiles(cacheModelId, true);
                            }
                        }
                    }
                    saveFilesCacheToSession();
                    
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
            } catch(e) {
                console.error('创建软链接失败:', e);
                alert('创建失败: ' + e.message);
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            restoreFilesCacheFromSession();
            restoreSearchState();
            refreshLocalModels();
            restoreDownloadingStates();
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
    model_id = data.get('model_id', '')
    
    if not download_url or not filename:
        return {"success": False, "message": "缺少必要参数"}
    
    def run_download():
        model_manager.download_model(download_url, filename, model_id)
    
    background_tasks.add_task(run_download)
    return {"success": True, "message": f"开始下载 {filename}"}

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

@router.post("/api/delete_partial")
async def delete_partial(request: Request):
    """删除部分下载的文件"""
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

@router.get("/api/local")
async def get_local_models():
    """获取本地已下载的模型列表（包括部分下载的文件）"""
    models = model_manager.get_local_models()
    
    partial_files = []
    for item in model_manager.models_dir.rglob('*.partial'):
        if item.is_file():
            size = item.stat().st_size
            size_gb = size / (1024 * 1024 * 1024)
            rel_path = item.relative_to(model_manager.models_dir)
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

@router.get("/api/progress")
async def get_download_progress(filename: str):
    """获取下载进度"""
    progress = model_manager.get_progress(filename)
    return progress