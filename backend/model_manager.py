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
                
                # 检查是否有不完整的文件
                if not is_downloaded and file_path.exists() and file_path.stat().st_size > 0:
                    has_partial = True
                
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
        """下载模型文件，支持断点续传和暂停"""
        file_path = self.get_file_path(model_id, filename)
        partial_path = file_path.parent / (file_path.name + '.partial')
        
        # 重置停止和暂停标志
        self.download_stop_flags[filename] = False
        self.download_paused[filename] = False
        
        # 检查文件是否已存在且完整
        if file_path.exists() and file_path.stat().st_size > 0:
            self.log(f"模型已存在: {file_path}")
            self.update_progress(filename, 100, "文件已存在", False)
            self.create_symlink_for_file(model_id, filename, file_path)
            if callback:
                callback(100, "文件已存在")
            # 延迟清除进度
            def delayed_clear():
                time.sleep(5)
                self.clear_progress(filename)
            threading.Thread(target=delayed_clear, daemon=True).start()
            return True
        
        # 检查是否有部分下载的文件
        resume_byte = 0
        download_path = file_path
        
        if partial_path.exists():
            resume_byte = partial_path.stat().st_size
            download_path = partial_path
            self.log(f"发现部分下载文件 (.partial)，大小 {resume_byte} 字节，从该位置续传")
        elif file_path.exists() and file_path.stat().st_size > 0:
            # 检查是否有不完整的文件（可能是之前下载中断的）
            resume_byte = file_path.stat().st_size
            download_path = file_path
            self.log(f"发现不完整文件，大小 {resume_byte} 字节，尝试续传")
        
        try:
            if resume_byte > 0:
                self.log(f"续传下载: {download_url} (从 {resume_byte} 字节处)")
            else:
                self.log(f"开始下载: {download_url}")
            self.log(f"保存路径: {download_path}")
            
            download_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建请求
            req = urllib.request.Request(download_url, headers={'User-Agent': 'LlamaPanel/1.0'})
            if resume_byte > 0:
                req.add_header('Range', f'bytes={resume_byte}-')
                self.log(f"设置 Range 头: bytes={resume_byte}-")
            
            with urllib.request.urlopen(req, timeout=3600) as response:
                # 获取总大小
                content_range = response.headers.get('Content-Range', '')
                if content_range:
                    # 格式: bytes 0-1234/5678
                    total_size = int(content_range.split('/')[-1])
                else:
                    # 如果是新下载，从 Content-Length 获取
                    content_length = response.headers.get('Content-Length', '0')
                    total_size = int(content_length) + resume_byte
                
                self.log(f"文件总大小: {total_size} 字节, 已下载: {resume_byte} 字节")
                
                downloaded = resume_byte
                last_percent = int(downloaded * 100 / total_size) if total_size > 0 else 0
                
                # 立即报告已有进度
                if resume_byte > 0 and total_size > 0:
                    initial_percent = int(resume_byte * 100 / total_size)
                    self.update_progress(filename, initial_percent, f"续传中... {initial_percent}%", True)
                    if callback:
                        callback(initial_percent, f"续传中... {initial_percent}%")
                    self.log(f"续传开始，当前进度: {initial_percent}%")
                else:
                    self.update_progress(filename, 0, "开始下载...", True)
                    if callback:
                        callback(0, "开始下载...")
                
                with open(download_path, 'ab') as f:
                    last_log_time = time.time()
                    while True:
                        # 检查是否收到停止信号
                        if self.download_stop_flags.get(filename, False):
                            self.log(f"下载已停止: {filename}")
                            self.update_progress(filename, last_percent, "已停止", False)
                            if callback:
                                callback(last_percent, "已停止")
                            # 删除部分下载的文件
                            if download_path.exists():
                                download_path.unlink()
                            return False
                        
                        # 检查是否收到暂停信号
                        if self.download_paused.get(filename, False):
                            self.log(f"下载已暂停: {filename}")
                            self.update_progress(filename, last_percent, "已暂停", False)
                            if callback:
                                callback(last_percent, "已暂停")
                            # 保留部分下载的文件（重命名为 .partial）
                            if download_path == file_path and download_path.exists():
                                shutil.move(str(download_path), str(partial_path))
                                self.log(f"已暂停，文件保存为: {partial_path}")
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
                                
                                # 每10秒记录一次日志，避免日志过多
                                current_time = time.time()
                                if current_time - last_log_time >= 10:
                                    self.log(f"下载进度 [{filename}]: {percent}% ({downloaded}/{total_size} bytes)")
                                    last_log_time = current_time
            
            # 下载完成，处理文件
            if download_path != file_path:
                shutil.move(str(download_path), str(file_path))
                self.log(f"重命名文件: {download_path} -> {file_path}")
            
            # 验证下载的文件大小
            if total_size > 0 and file_path.stat().st_size != total_size:
                self.log(f"文件大小不匹配: 本地={file_path.stat().st_size}, 远程={total_size}")
                file_path.unlink()
                raise Exception("文件大小不匹配")
            
            # 创建软链接
            self.create_symlink_for_file(model_id, filename, file_path)
            
            self.log(f"下载完成: {file_path}")
            self.update_progress(filename, 100, "下载完成", False)
            if callback:
                callback(100, "下载完成")
            
            # 延迟清除进度，让前端有时间获取完成状态
            def delayed_clear():
                time.sleep(5)
                self.clear_progress(filename)
            threading.Thread(target=delayed_clear, daemon=True).start()
            return True
            
        except urllib.error.HTTPError as e:
            self.log(f"HTTP错误: {e.code} - {e.reason}")
            if e.code == 416:  # Range Not Satisfiable (文件已完整)
                self.log("Range 请求返回 416，文件可能已完整")
                if download_path.exists() and download_path != file_path:
                    shutil.move(str(download_path), str(file_path))
                if file_path.exists():
                    self.update_progress(filename, 100, "下载完成", False)
                    if callback:
                        callback(100, "下载完成")
                    self.create_symlink_for_file(model_id, filename, file_path)
                    # 延迟清除进度
                    def delayed_clear():
                        time.sleep(5)
                        self.clear_progress(filename)
                    threading.Thread(target=delayed_clear, daemon=True).start()
                    return True
            self.update_progress(filename, -1, f"下载失败: HTTP {e.code}", False)
            if callback:
                callback(-1, f"HTTP错误: {e.code}")
            return False
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
            
            # 停止正在进行的下载
            self.stop_download(filename)
            time.sleep(0.5)
            
            # 删除部分下载文件 (.partial)
            for item in self.models_dir.rglob('*.partial'):
                if filename in str(item) or item.name.startswith(filename.replace('.gguf', '')):
                    item.unlink()
                    self.log(f"删除部分下载文件: {item}")
                    deleted = True
            
            # 尝试直接删除
            direct_path = self.models_dir / filename
            if direct_path.exists():
                direct_path.unlink()
                self.log(f"删除模型: {direct_path}")
                deleted = True
            
            # 尝试在子目录中查找并删除
            for item in self.models_dir.iterdir():
                if item.is_dir():
                    file_path = item / filename
                    if file_path.exists():
                        file_path.unlink()
                        self.log(f"删除模型: {file_path}")
                        deleted = True
                    # 也尝试匹配 mmproj 文件
                    for subfile in item.glob('*.gguf'):
                        if subfile.name == filename:
                            subfile.unlink()
                            self.log(f"删除模型: {subfile}")
                            deleted = True
            
            # 清理进度记录
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
    
    def cleanup_incomplete_files(self) -> int:
        """清理不完整的文件"""
        cleaned = 0
        # 删除所有 .partial 文件
        for item in self.models_dir.rglob('*.partial'):
            self.log(f"清理部分下载文件: {item}")
            item.unlink()
            cleaned += 1
        # 删除小于 1MB 的不完整 gguf 文件
        for item in self.models_dir.rglob('*.gguf'):
            if item.is_file() and item.stat().st_size < 1024 * 1024:
                self.log(f"清理不完整文件: {item} ({item.stat().st_size} bytes)")
                item.unlink()
                cleaned += 1
        return cleaned