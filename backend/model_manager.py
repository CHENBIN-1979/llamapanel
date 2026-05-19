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
        self.links_dir = self.base_dir / "model_links"       # 独立的软链接目录
        self.log_file = self.base_dir / "logs" / "models.log"
        
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
        with self.progress_lock:
            self.download_progress[filename] = {
                'percent': percent,
                'status': status,
                'downloading': downloading,
                'updated_at': time.time()
            }
            self.log(f"进度更新 [{filename}]: {percent}% - {status}")
    
    def get_progress(self, filename: str) -> Dict:
        with self.progress_lock:
            if filename in self.download_progress:
                return self.download_progress[filename]
            return {'percent': 0, 'status': '未开始', 'downloading': False}
    
    def clear_progress(self, filename: str):
        with self.progress_lock:
            if filename in self.download_progress:
                del self.download_progress[filename]
    
    def get_model_folder(self, model_id: str) -> Path:
        """获取模型专属文件夹路径"""
        # 将 model_id 中的 / 替换为 _，作为文件夹名
        folder_name = model_id.replace('/', '_')
        folder_path = self.models_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
    
    def get_file_path(self, model_id: str, filename: str) -> Path:
        """获取文件的完整存储路径（按模型分类存储）"""
        # 提取文件名（可能包含路径）
        base_filename = filename.split('/')[-1]
        
        # 判断是否是 mmproj 文件
        is_mmproj = 'mmproj' in base_filename.lower()
        
        if is_mmproj:
            # mmproj 文件放到模型专属文件夹
            folder = self.get_model_folder(model_id)
            return folder / base_filename
        else:
            # 普通 GGUF 模型文件直接放在 models 目录
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', base_filename)
            return self.models_dir / safe_filename
    
    def get_symlink_path(self, model_id: str, filename: str) -> Path:
        """获取软链接路径"""
        base_filename = filename.split('/')[-1]
        is_mmproj = 'mmproj' in base_filename.lower()
        
        if is_mmproj:
            # mmproj 文件的软链接也放到模型专属子目录
            folder_name = model_id.replace('/', '_')
            link_folder = self.links_dir / folder_name
            link_folder.mkdir(parents=True, exist_ok=True)
            return link_folder / base_filename
        else:
            # 普通模型文件的软链接直接放在 links_dir
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', base_filename)
            return self.links_dir / safe_filename
    
    def search_huggingface_models(self, query: str, limit: int = 30) -> List[Dict]:
        results = []
        search_query = f"{query} GGUF"
        self.log(f"原始搜索词: '{query}', 实际搜索词: '{search_query}'")
        
        try:
            search_url = f"https://huggingface.co/api/models?search={urllib.parse.quote(search_query)}&sort=downloads&direction=-1&limit={limit}"
            req = urllib.request.Request(search_url, headers={'User-Agent': 'LlamaPanel/1.0'})
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
        try:
            api_url = f"https://huggingface.co/api/models/{model_id}"
            req = urllib.request.Request(api_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            siblings = data.get('siblings', [])
            gguf_files = []
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
            
            for file_info in file_list:
                filename = file_info['filename']
                download_url = file_info['download_url']
                api_size = file_info['api_size']
                
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
                
                # 检查文件是否已下载
                file_path = self.get_file_path(model_id, filename)
                is_downloaded = file_path.exists()
                
                gguf_files.append({
                    'filename': filename.split('/')[-1],  # 只显示文件名
                    'full_path': filename,  # 完整路径
                    'size': size,
                    'size_str': size_str,
                    'download_url': download_url,
                    'is_downloaded': is_downloaded
                })
            
            gguf_files.sort(key=lambda x: x['size'], reverse=True)
            return gguf_files
        except Exception as e:
            self.log(f"获取模型文件失败 {model_id}: {e}")
            return []
    
    def download_model(self, download_url: str, filename: str, model_id: str, callback=None) -> bool:
        """下载模型文件到对应目录"""
        # 获取存储路径
        file_path = self.get_file_path(model_id, filename)
        
        if file_path.exists():
            self.log(f"模型已存在: {file_path}")
            self.update_progress(filename, 100, "文件已存在", False)
            self.create_symlink_for_file(model_id, filename, file_path)
            return True
        
        try:
            self.log(f"开始下载: {download_url}")
            self.log(f"保存路径: {file_path}")
            self.update_progress(filename, 0, "开始下载...", True)
            
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            with urllib.request.urlopen(req, timeout=3600) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                last_percent = 0
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            if percent > last_percent:
                                last_percent = percent
                                self.update_progress(filename, percent, f"下载中... {percent}%", True)
            
            # 创建软链接
            self.create_symlink_for_file(model_id, filename, file_path)
            
            self.log(f"下载完成: {file_path}")
            self.update_progress(filename, 100, "下载完成", False)
            
            def clear_after_delay():
                time.sleep(5)
                self.clear_progress(filename)
            threading.Thread(target=clear_after_delay, daemon=True).start()
            return True
        except Exception as e:
            self.log(f"下载失败: {e}")
            self.update_progress(filename, -1, f"下载失败: {e}", False)
            if file_path.exists():
                file_path.unlink()
            return False
    
    def create_symlink_for_file(self, model_id: str, filename: str, file_path: Path) -> bool:
        """为文件创建软链接"""
        try:
            link_path = self.get_symlink_path(model_id, filename)
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(file_path)
            self.log(f"创建软链接: {link_path} -> {file_path}")
            return True
        except Exception as e:
            self.log(f"创建软链接失败: {e}")
            return False
    
    def get_local_models(self) -> List[Dict]:
        """获取已下载的模型文件列表（递归查找）"""
        models = []
        if self.models_dir.exists():
            for item in self.models_dir.iterdir():
                if item.is_file() and item.suffix == '.gguf':
                    # 根目录下的模型文件
                    size = item.stat().st_size
                    size_gb = size / (1024 * 1024 * 1024)
                    models.append({
                        'name': item.name,
                        'path': str(item),
                        'size': size,
                        'size_str': f"{size_gb:.2f} GB",
                        'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.stat().st_mtime))
                    })
                elif item.is_dir():
                    # 子目录中的模型文件
                    for subitem in item.iterdir():
                        if subitem.is_file() and subitem.suffix == '.gguf':
                            size = subitem.stat().st_size
                            size_gb = size / (1024 * 1024 * 1024)
                            models.append({
                                'name': f"{item.name}/{subitem.name}",
                                'path': str(subitem),
                                'size': size,
                                'size_str': f"{size_gb:.2f} GB",
                                'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(subitem.stat().st_mtime))
                            })
        return sorted(models, key=lambda x: x['name'])
    
    def delete_model(self, filename: str) -> bool:
        """删除模型文件及其软链接（支持路径格式）"""
        try:
            # 尝试多种路径格式
            paths_to_try = [
                self.models_dir / filename,  # 根目录
                self.models_dir / filename.replace('/', '_'),  # 可能是子目录格式
            ]
            
            # 也尝试在子目录中查找
            for item in self.models_dir.iterdir():
                if item.is_dir():
                    if (item / filename).exists():
                        paths_to_try.append(item / filename)
            
            deleted = False
            for file_path in paths_to_try:
                if file_path.exists():
                    file_path.unlink()
                    self.log(f"删除模型: {file_path}")
                    deleted = True
                    break
            
            # 删除对应的软链接
            for link_item in self.links_dir.iterdir():
                if link_item.is_symlink() and link_item.resolve() == file_path:
                    link_item.unlink()
                    self.log(f"删除软链接: {link_item}")
                elif link_item.is_dir():
                    for sublink in link_item.iterdir():
                        if sublink.is_symlink() and sublink.resolve() == file_path:
                            sublink.unlink()
                            self.log(f"删除软链接: {sublink}")
            
            return deleted
        except Exception as e:
            self.log(f"删除失败: {e}")
            return False
    
    def create_symlinks(self) -> int:
        """为所有模型创建软链接"""
        count = 0
        # 递归查找所有模型文件并创建软链接
        for model in self.get_local_models():
            file_path = Path(model['path'])
            # 从路径中提取 model_id 和 filename
            parts = file_path.relative_to(self.models_dir).parts
            if len(parts) == 2:
                # 子目录中的文件：model_dir/filename
                model_id = parts[0].replace('_', '/')
                filename = parts[1]
                if self.create_symlink_for_file(model_id, filename, file_path):
                    count += 1
            else:
                # 根目录的文件
                filename = parts[0]
                # 无法确定 model_id，直接创建软链接到根目录
                link_path = self.links_dir / filename
                if not link_path.exists():
                    link_path.symlink_to(file_path)
                    count += 1
        return count
    
    def is_model_downloaded(self, model_id: str, filename: str) -> bool:
        """检查模型是否已下载"""
        file_path = self.get_file_path(model_id, filename)
        return file_path.exists()