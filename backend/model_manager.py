#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Optional, List, Dict

class ModelManager:
    def __init__(self):
        self.base_dir = Path("/opt/llamapanel")
        self.models_dir = self.base_dir / "models"
        self.llama_models_dir = self.base_dir / "llama.cpp" / "models"
        self.downloads_dir = self.base_dir / "downloads"
        self.log_file = self.base_dir / "logs" / "models.log"
        
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.llama_models_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    def search_huggingface_models(self, query: str, limit: int = 20) -> List[Dict]:
        """搜索 HuggingFace 上的 GGUF 模型"""
        results = []
        
        # 方法1：使用 HuggingFace Hub API
        try:
            search_url = f"https://huggingface.co/api/models?search={urllib.parse.quote(query)}&sort=downloads&direction=-1&limit={limit}"
            
            req = urllib.request.Request(
                search_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            for model in data:
                model_id = model.get('modelId', '')
                if any(x in model_id.lower() for x in ['gguf', 'ggml', 'llama', 'qwen', 'mistral', 'gemma', 'phi']):
                    results.append({
                        'id': model_id,
                        'name': model_id.split('/')[-1],
                        'author': model_id.split('/')[0],
                        'likes': model.get('likes', 0),
                        'downloads': model.get('downloads', 0),
                        'tags': model.get('tags', [])
                    })
            
            if results:
                self.log(f"搜索 '{query}' 找到 {len(results)} 个模型")
                return results
        except Exception as e:
            self.log(f"HuggingFace API 搜索失败: {e}")
        
        # 方法2：使用预定义的常用模型列表
        popular_models = [
            {'id': 'TheBloke/Llama-2-7B-Chat-GGUF', 'name': 'Llama-2-7B-Chat-GGUF', 'author': 'TheBloke', 'likes': 1000, 'downloads': 100000},
            {'id': 'TheBloke/Mistral-7B-Instruct-v0.2-GGUF', 'name': 'Mistral-7B-Instruct-v0.2-GGUF', 'author': 'TheBloke', 'likes': 800, 'downloads': 80000},
            {'id': 'TheBloke/Qwen-7B-Chat-GGUF', 'name': 'Qwen-7B-Chat-GGUF', 'author': 'TheBloke', 'likes': 600, 'downloads': 60000},
            {'id': 'TheBloke/gemma-2b-it-GGUF', 'name': 'gemma-2b-it-GGUF', 'author': 'TheBloke', 'likes': 400, 'downloads': 40000},
            {'id': 'TheBloke/CodeLlama-7B-Instruct-GGUF', 'name': 'CodeLlama-7B-Instruct-GGUF', 'author': 'TheBloke', 'likes': 500, 'downloads': 50000},
            {'id': 'TheBloke/Phi-3-mini-4k-instruct-GGUF', 'name': 'Phi-3-mini-4k-instruct-GGUF', 'author': 'TheBloke', 'likes': 300, 'downloads': 30000},
            {'id': 'second-state/StarCoder2-7B-GGUF', 'name': 'StarCoder2-7B-GGUF', 'author': 'second-state', 'likes': 200, 'downloads': 20000},
            {'id': 'mradermacher/Llama-3.2-1B-Instruct-GGUF', 'name': 'Llama-3.2-1B-Instruct-GGUF', 'author': 'mradermacher', 'likes': 150, 'downloads': 15000},
            {'id': 'bartowski/Llama-3.2-3B-Instruct-GGUF', 'name': 'Llama-3.2-3B-Instruct-GGUF', 'author': 'bartowski', 'likes': 100, 'downloads': 10000},
            {'id': 'QuantFactory/DeepSeek-Coder-V2-Lite-Instruct-GGUF', 'name': 'DeepSeek-Coder-V2-Lite-Instruct-GGUF', 'author': 'QuantFactory', 'likes': 80, 'downloads': 8000},
        ]
        
        query_lower = query.lower()
        for model in popular_models:
            if query_lower in model['id'].lower() or query_lower in model['name'].lower():
                results.append({
                    'id': model['id'],
                    'name': model['name'],
                    'author': model['author'],
                    'likes': model.get('likes', 0),
                    'downloads': model.get('downloads', 0),
                    'tags': []
                })
        
        if not results and query:
            # 返回前10个热门模型
            for model in popular_models[:10]:
                results.append({
                    'id': model['id'],
                    'name': model['name'],
                    'author': model['author'],
                    'likes': model.get('likes', 0),
                    'downloads': model.get('downloads', 0),
                    'tags': []
                })
        
        self.log(f"备用搜索 '{query}' 找到 {len(results)} 个模型")
        return results[:limit]
    
    def get_model_files(self, model_id: str) -> List[Dict]:
        """获取模型的所有 GGUF 文件"""
        try:
            api_url = f"https://huggingface.co/api/models/{model_id}"
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            siblings = data.get('siblings', [])
            gguf_files = []
            
            for sibling in siblings:
                filename = sibling.get('rfilename', '')
                if filename.endswith('.gguf'):
                    size = sibling.get('size', 0)
                    size_mb = size / (1024 * 1024)
                    size_gb = size / (1024 * 1024 * 1024)
                    
                    if size_gb >= 1:
                        size_str = f"{size_gb:.2f} GB"
                    else:
                        size_str = f"{size_mb:.0f} MB"
                    
                    gguf_files.append({
                        'filename': filename,
                        'size': size,
                        'size_str': size_str,
                        'download_url': f"https://huggingface.co/{model_id}/resolve/main/{filename}"
                    })
            
            return gguf_files
        except Exception as e:
            self.log(f"获取模型文件失败: {e}")
            return []
    
    def download_model(self, download_url: str, filename: str, callback=None) -> bool:
        """下载模型文件，支持进度回调"""
        try:
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
            download_path = self.downloads_dir / safe_filename
            final_path = self.models_dir / safe_filename
            
            if final_path.exists():
                self.log(f"模型已存在: {safe_filename}")
                if callback:
                    callback(100, "文件已存在")
                return True
            
            self.log(f"开始下载: {download_url}")
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req, timeout=60) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                
                with open(download_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0 and callback:
                            percent = int(downloaded * 100 / total_size)
                            callback(percent, f"下载中... {percent}%")
            
            shutil.move(str(download_path), str(final_path))
            
            link_path = self.llama_models_dir / safe_filename
            if link_path.exists() and link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(final_path)
            
            self.log(f"下载完成: {safe_filename}")
            if callback:
                callback(100, "下载完成")
            
            return True
            
        except Exception as e:
            self.log(f"下载失败: {e}")
            if callback:
                callback(-1, f"下载失败: {e}")
            return False
    
    def get_local_models(self) -> List[Dict]:
        """获取已下载的模型列表"""
        models = []
        if self.models_dir.exists():
            for f in self.models_dir.iterdir():
                if f.is_file() and f.suffix == '.gguf':
                    size = f.stat().st_size
                    size_gb = size / (1024 * 1024 * 1024)
                    models.append({
                        'name': f.name,
                        'path': str(f),
                        'size': size,
                        'size_str': f"{size_gb:.2f} GB",
                        'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
                    })
        return sorted(models, key=lambda x: x['name'])
    
    def delete_model(self, filename: str) -> bool:
        """删除模型文件"""
        try:
            model_path = self.models_dir / filename
            if model_path.exists():
                model_path.unlink()
                self.log(f"删除模型: {filename}")
            
            link_path = self.llama_models_dir / filename
            if link_path.exists() and link_path.is_symlink():
                link_path.unlink()
            
            return True
        except Exception as e:
            self.log(f"删除失败: {e}")
            return False
    
    def create_symlinks(self) -> int:
        """为所有模型创建软链接"""
        count = 0
        for model in self.get_local_models():
            model_path = Path(model['path'])
            link_path = self.llama_models_dir / model_path.name
            if not link_path.exists():
                link_path.symlink_to(model_path)
                count += 1
                self.log(f"创建软链接: {link_path} -> {model_path}")
        return count