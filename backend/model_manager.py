#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
import re
import json
import urllib.request
import urllib.parse
import threading
from pathlib import Path
from typing import Optional, List, Dict

class ModelManager:
    def __init__(self):
        self.base_dir = Path("/opt/llamapanel")
        self.models_dir = self.base_dir / "models"           # 模型实际存储目录
        self.links_dir = self.base_dir / "model_links"       # 独立的软链接目录（不依赖llama.cpp）
        self.log_file = self.base_dir / "logs" / "models.log"
        
        # 下载进度存储 {filename: {'percent': int, 'status': str, 'downloading': bool}}
        self.download_progress = {}
        self.progress_lock = threading.Lock()
        
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.links_dir.mkdir(parents=True, exist_ok=True)
        
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    def update_progress(self, filename: str, percent: int, status: str, downloading: bool = True):
        """更新下载进度"""
        with self.progress_lock:
            self.download_progress[filename] = {
                'percent': percent,
                'status': status,
                'downloading': downloading,
                'updated_at': time.time()
            }
    
    def get_progress(self, filename: str) -> Dict:
        """获取下载进度"""
        with self.progress_lock:
            if filename in self.download_progress:
                return self.download_progress[filename]
            return {'percent': 0, 'status': '未开始', 'downloading': False}
    
    def clear_progress(self, filename: str):
        """清除下载进度记录"""
        with self.progress_lock:
            if filename in self.download_progress:
                del self.download_progress[filename]
    
    def search_huggingface_models(self, query: str, limit: int = 30) -> List[Dict]:
        """搜索 HuggingFace 上的 GGUF 模型（自动添加 GGUF 关键词）"""
        results = []
        
        # 自动添加 GGUF 关键词，确保只搜索可下载的量化模型
        search_query = f"{query} GGUF"
        self.log(f"原始搜索词: '{query}', 实际搜索词: '{search_query}'")
        
        try:
            search_url = f"https://huggingface.co/api/models?search={urllib.parse.quote(search_query)}&sort=downloads&direction=-1&limit={limit}"
            
            req = urllib.request.Request(
                search_url,
                headers={'User-Agent': 'LlamaPanel/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            for model in data:
                model_id = model.get('modelId', '')
                if not model_id:
                    continue
                
                results.append({
                    'id': model_id,
                    'name': model_id.split('/')[-1],
                    'author': model_id.split('/')[0],
                    'likes': model.get('likes', 0),
                    'downloads': model.get('downloads', 0),
                    'tags': model.get('tags', [])
                })
            
            self.log(f"搜索 '{query}' 成功，找到 {len(results)} 个 GGUF 模型")
            return results
            
        except Exception as e:
            self.log(f"HuggingFace API 搜索失败: {e}")
            return []
    
    def get_file_size_from_url(self, url: str) -> tuple:
        """通过 HEAD 请求获取文件大小"""
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'LlamaPanel/1.0')
            with urllib.request.urlopen(req, timeout=10) as response:
                size = int(response.headers.get('Content-Length', 0))
                return size, True
        except Exception as e:
            self.log(f"获取文件大小失败 {url}: {e}")
            return 0, False
    
    def format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size <= 0:
            return "未知大小"
        
        size_gb = size / (1024 * 1024 * 1024)
        if size_gb >= 1:
            return f"{size_gb:.2f} GB"
        
        size_mb = size / (1024 * 1024)
        if size_mb >= 1:
            return f"{size_mb:.0f} MB"
        
        size_kb = size / 1024
        if size_kb >= 1:
            return f"{size_kb:.0f} KB"
        
        return f"{size} B"
    
    def get_model_files(self, model_id: str) -> List[Dict]:
        """获取模型的所有 GGUF 文件（通过 HEAD 请求获取准确大小）"""
        try:
            api_url = f"https://huggingface.co/api/models/{model_id}"
            req = urllib.request.Request(
                api_url,
                headers={'User-Agent': 'LlamaPanel/1.0'}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            siblings = data.get('siblings', [])
            gguf_files = []
            
            # 先收集所有 GGUF 文件名和下载 URL
            file_list = []
            for sibling in siblings:
                filename = sibling.get('rfilename', '')
                if filename.endswith('.gguf'):
                    download_url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"
                    file_list.append({
                        'filename': filename,
                        'download_url': download_url,
                        'api_size': sibling.get('size', 0)
                    })
            
            # 获取每个文件的准确大小
            self.log(f"正在获取 {len(file_list)} 个文件的大小信息...")
            
            for file_info in file_list:
                filename = file_info['filename']
                download_url = file_info['download_url']
                api_size = file_info['api_size']
                
                # 优先使用 HEAD 请求获取准确大小
                real_size, success = self.get_file_size_from_url(download_url)
                
                if success and real_size > 0:
                    size = real_size
                    size_str = self.format_size(size)
                elif api_size > 0:
                    size = api_size
                    size_str = self.format_size(size)
                else:
                    size = 0
                    size_str = "获取中..."
                
                gguf_files.append({
                    'filename': filename,
                    'size': size,
                    'size_str': size_str,
                    'download_url': download_url
                })
            
            # 按文件大小排序（大的在前）
            gguf_files.sort(key=lambda x: x['size'], reverse=True)
            
            if gguf_files:
                self.log(f"获取模型 {model_id} 文件成功，找到 {len(gguf_files)} 个 GGUF 文件")
            else:
                self.log(f"模型 {model_id} 没有 GGUF 文件")
            
            return gguf_files
        except Exception as e:
            self.log(f"获取模型文件失败 {model_id}: {e}")
            return []
    
    def download_model(self, download_url: str, filename: str, callback=None) -> bool:
        """直接下载模型到 models 目录（无需临时目录），下载完成后自动创建软链接"""
        try:
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
            final_path = self.models_dir / safe_filename
            
            if final_path.exists():
                self.log(f"模型已存在: {safe_filename}")
                self.update_progress(safe_filename, 100, "文件已存在", False)
                if callback:
                    callback(100, "文件已存在")
                return True
            
            self.log(f"开始下载: {download_url}")
            self.log(f"保存路径: {final_path}")
            self.update_progress(safe_filename, 0, "开始下载...", True)
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            
            with urllib.request.urlopen(req, timeout=3600) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                last_percent = 0
                
                with open(final_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            # 每 2% 更新一次进度，减少日志
                            if percent != last_percent:
                                last_percent = percent
                                self.update_progress(safe_filename, percent, f"下载中... {percent}%", True)
                                if callback:
                                    callback(percent, f"下载中... {percent}%")
            
            # 下载完成后自动创建软链接到独立目录
            self.create_symlink_for_model(safe_filename)
            
            self.log(f"下载完成: {safe_filename}")
            self.update_progress(safe_filename, 100, "下载完成", False)
            if callback:
                callback(100, "下载完成")
            
            # 5秒后清除进度记录
            def clear_after_delay():
                time.sleep(5)
                self.clear_progress(safe_filename)
            
            threading.Thread(target=clear_after_delay, daemon=True).start()
            
            return True
            
        except Exception as e:
            self.log(f"下载失败: {e}")
            self.update_progress(safe_filename, -1, f"下载失败: {e}", False)
            if callback:
                callback(-1, f"下载失败: {e}")
            return False
    
    def create_symlink_for_model(self, filename: str) -> bool:
        """为单个模型创建软链接到独立目录"""
        try:
            model_path = self.models_dir / filename
            if not model_path.exists():
                self.log(f"模型文件不存在: {filename}")
                return False
            
            link_path = self.links_dir / filename
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            
            link_path.symlink_to(model_path)
            self.log(f"创建软链接: {link_path} -> {model_path}")
            return True
        except Exception as e:
            self.log(f"创建软链接失败: {e}")
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
        """删除模型文件及其软链接"""
        try:
            model_path = self.models_dir / filename
            if model_path.exists():
                model_path.unlink()
                self.log(f"删除模型: {filename}")
            
            # 删除软链接
            link_path = self.links_dir / filename
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
                self.log(f"删除软链接: {link_path}")
            
            return True
        except Exception as e:
            self.log(f"删除失败: {e}")
            return False
    
    def create_symlinks(self) -> int:
        """为所有模型创建软链接到独立目录"""
        count = 0
        for model in self.get_local_models():
            if self.create_symlink_for_model(model['name']):
                count += 1
        self.log(f"共创建 {count} 个软链接到 {self.links_dir}")
        return count
    
    def get_links_dir(self) -> str:
        """获取软链接目录路径"""
        return str(self.links_dir)