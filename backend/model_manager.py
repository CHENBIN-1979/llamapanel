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
        self.models_dir = self.base_dir / "models"  # 模型存储目录（独立）
        self.llama_models_dir = self.base_dir / "llama.cpp" / "models"  # llama.cpp 的模型目录
        self.downloads_dir = self.base_dir / "downloads"  # 临时下载目录
        self.log_file = self.base_dir / "logs" / "models.log"
        
        # 创建目录
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
        try:
            # 使用 HuggingFace Hub API 搜索
            search_url = f"https://huggingface.co/api/models?search={urllib.parse.quote(query)}&limit={limit}"
            
            req = urllib.request.Request(
                search_url,
                headers={'User-Agent': 'LlamaPanel/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            for model in data:
                model_id = model.get('modelId', '')
                # 筛选包含 GGUF 的模型
                if 'gguf' in model_id.lower() or 'ggml' in model_id.lower():
                    results.append({
                        'id': model_id,
                        'name': model_id.split('/')[-1],
                        'author': model_id.split('/')[0],
                        'likes': model.get('likes', 0),
                        'downloads': model.get('downloads', 0),
                        'tags': model.get('tags', [])
                    })
            
            self.log(f"搜索 '{query}' 找到 {len(results)} 个 GGUF 模型")
            return results
        except Exception as e:
            self.log(f"搜索模型失败: {e}")
            return []
    
    def get_model_files(self, model_id: str) -> List[Dict]:
        """获取模型的所有 GGUF 文件"""
        try:
            api_url = f"https://huggingface.co/api/models/{model_id}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            siblings = data.get('siblings', [])
            gguf_files = []
            
            for sibling in siblings:
                filename = sibling.get('rfilename', '')
                if filename.endswith('.gguf'):
                    # 获取文件大小
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
            # 安全的文件名
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
            download_path = self.downloads_dir / safe_filename
            final_path = self.models_dir / safe_filename
            
            # 检查是否已存在
            if final_path.exists():
                self.log(f"模型已存在: {safe_filename}")
                if callback:
                    callback(100, "文件已存在")
                return True
            
            self.log(f"开始下载: {download_url}")
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            
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
            
            # 移动到最终目录
            shutil.move(str(download_path), str(final_path))
            
            # 创建软链接到 llama.cpp/models/
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
            
            # 删除软链接
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