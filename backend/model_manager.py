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
        self.models_dir = self.base_dir / "models"
        self.links_dir = self.base_dir / "model_links"
        self.log_file = self.base_dir / "logs" / "models.log"
        
        self.download_progress = {}
        self.download_threads = {}
        self.download_stop_flags = {}
        self.download_paused = {}
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
            if filename in self.download_stop_flags:
                del self.download_stop_flags[filename]
            if filename in self.download_paused:
                del self.download_paused[filename]
    
    def stop_download(self, filename: str) -> bool:
        with self.progress_lock:
            self.download_stop_flags[filename] = True
            self.log(f"停止下载信号已发送: {filename}")
            return True
    
    def pause_download(self, filename: str) -> bool:
        with self.progress_lock:
            self.download_paused[filename] = True
            self.log(f"暂停下载信号已发送: {filename}")
            return True
    
    def get_model_folder(self, model_id: str) -> Path:
        folder_name = model_id.replace('/', '_')
        folder_path = self.models_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
    
    def get_file_path(self, model_id: str, filename: str) -> Path:
        base_filename = filename.split('/')[-1]
        is_mmproj = 'mmproj' in base_filename.lower()
        
        if is_mmproj:
            folder = self.get_model_folder(model_id)
            return folder / base_filename
        else:
            safe_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', base_filename)
            return self.models_dir / safe_filename
    
    def get_symlink_path(self, model_id: str, filename: str) -> Path:
        base_filename = filename.split('/')[-1]
        is_mmproj = 'mmproj' in base_filename.lower()
        
        if is_mmproj:
            folder_name = model_id.replace('/', '_')
            link_folder = self.links_dir / folder_name
            link_folder.mkdir(parents=True, exist_ok=True)
            return link_folder / base_filename
        else:
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
                
                file_path = self.get_file_path(model_id, filename)
                is_downloaded = file_path.exists() and file_path.stat().st_size > 0
                
                partial_path = file_path.parent / (file_path.name + '.partial')
                has_partial = partial_path.exists() and partial_path.stat().st_size > 0
                
                if is_downloaded and size > 0:
                    local_size = file_path.stat().st_size
                    if abs(local_size - size) > size * 0.1:
                        is_downloaded = False
                
                gguf_files.append({
                    'filename': filename.split('/')[-1],
                    'full_path': filename,
                    'size': size,
                    'size_str': size_str,
                    'download_url': download_url,
                    'is_downloaded': is_downloaded,
                    'has_partial': has_partial
                })
            
            gguf_files.sort(key=lambda x: x['size'], reverse=True)
            return gguf_files
        except Exception as e:
            self.log(f"获取模型文件失败 {model_id}: {e}")
            return []
    
    def download_model(self, download_url: str, filename: str, model_id: str, callback=None) -> bool:
        file_path = self.get_file_path(model_id, filename)
        partial_path = file_path.parent / (file_path.name + '.partial')
        
        self.download_stop_flags[filename] = False
        self.download_paused[filename] = False
        
        if file_path.exists() and file_path.stat().st_size > 0:
            self.log(f"模型已存在: {file_path}")
            self.update_progress(filename, 100, "文件已存在", False)
            self.create_symlink_for_file(model_id, filename, file_path)
            if callback:
                callback(100, "文件已存在")
            self.clear_progress(filename)
            return True
        
        resume_byte = 0
        download_path = file_path
        if partial_path.exists():
            resume_byte = partial_path.stat().st_size
            download_path = partial_path
            self.log(f"发现部分下载文件，从 {resume_byte} 字节处续传")
        
        try:
            self.log(f"开始下载: {download_url}")
            self.log(f"保存路径: {download_path}")
            self.update_progress(filename, 0, "开始下载...", True)
            if callback:
                callback(0, "开始下载...")
            
            download_path.parent.mkdir(parents=True, exist_ok=True)
            
            req = urllib.request.Request(download_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            if resume_byte > 0:
                req.add_header('Range', f'bytes={resume_byte}-')
            
            with urllib.request.urlopen(req, timeout=3600) as response:
                content_range = response.headers.get('Content-Range', '')
                if content_range:
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = int(response.headers.get('Content-Length', 0)) + resume_byte
                
                downloaded = resume_byte
                last_percent = int(downloaded * 100 / total_size) if total_size > 0 else 0
                
                if resume_byte > 0 and total_size > 0:
                    initial_percent = int(resume_byte * 100 / total_size)
                    self.update_progress(filename, initial_percent, f"续传中... {initial_percent}%", True)
                    if callback:
                        callback(initial_percent, f"续传中... {initial_percent}%")
                
                with open(download_path, 'ab') as f:
                    while True:
                        if self.download_stop_flags.get(filename, False):
                            self.log(f"下载已停止: {filename}")
                            self.update_progress(filename, last_percent, "已停止", False)
                            if callback:
                                callback(last_percent, "已停止")
                            if download_path.exists():
                                download_path.unlink()
                            return False
                        
                        if self.download_paused.get(filename, False):
                            self.log(f"下载已暂停: {filename}")
                            self.update_progress(filename, last_percent, "已暂停", False)
                            if callback:
                                callback(last_percent, "已暂停")
                            return False
                        
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
                                if callback:
                                    callback(percent, f"下载中... {percent}%")
                                self.log(f"下载进度 [{filename}]: {percent}% ({downloaded}/{total_size} bytes)")
            
            if download_path != file_path:
                shutil.move(str(download_path), str(file_path))
            
            if total_size > 0 and file_path.stat().st_size != total_size:
                self.log(f"文件大小不匹配: 本地={file_path.stat().st_size}, 远程={total_size}")
                file_path.unlink()
                raise Exception("文件大小不匹配")
            
            self.create_symlink_for_file(model_id, filename, file_path)
            
            self.log(f"下载完成: {file_path}")
            self.update_progress(filename, 100, "下载完成", False)
            if callback:
                callback(100, "下载完成")
            
            self.clear_progress(filename)
            return True
            
        except Exception as e:
            self.log(f"下载失败: {e}")
            self.update_progress(filename, -1, f"下载失败: {e}", False)
            if callback:
                callback(-1, f"下载失败: {e}")
            return False
    
    def create_symlink_for_file(self, model_id: str, filename: str, file_path: Path) -> bool:
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
        models = []
        if self.models_dir.exists():
            for item in self.models_dir.rglob('*.gguf'):
                if item.is_file():
                    size = item.stat().st_size
                    size_gb = size / (1024 * 1024 * 1024)
                    rel_path = item.relative_to(self.models_dir)
                    models.append({
                        'name': str(rel_path),
                        'path': str(item),
                        'size': size,
                        'size_str': f"{size_gb:.2f} GB",
                        'modified': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.stat().st_mtime))
                    })
        return sorted(models, key=lambda x: x['name'])
    
    def delete_model(self, filename: str) -> bool:
        try:
            deleted = False
            
            self.stop_download(filename)
            time.sleep(0.5)
            
            for item in self.models_dir.rglob('*.partial'):
                if filename in str(item):
                    item.unlink()
                    self.log(f"删除部分下载文件: {item}")
                    deleted = True
            
            direct_path = self.models_dir / filename
            if direct_path.exists():
                direct_path.unlink()
                self.log(f"删除模型: {direct_path}")
                deleted = True
            
            for item in self.models_dir.iterdir():
                if item.is_dir():
                    file_path = item / filename
                    if file_path.exists():
                        file_path.unlink()
                        self.log(f"删除模型: {file_path}")
                        deleted = True
            
            self.clear_progress(filename)
            return deleted
        except Exception as e:
            self.log(f"删除失败: {e}")
            return False
    
    def create_symlinks(self) -> int:
        count = 0
        for model in self.get_local_models():
            file_path = Path(model['path'])
            rel_path = file_path.relative_to(self.models_dir)
            parts = rel_path.parts
            
            if len(parts) == 2:
                model_id = parts[0].replace('_', '/')
                filename = parts[1]
                if self.create_symlink_for_file(model_id, filename, file_path):
                    count += 1
            else:
                filename = parts[0]
                model_id = "unknown"
                if self.create_symlink_for_file(model_id, filename, file_path):
                    count += 1
        return count