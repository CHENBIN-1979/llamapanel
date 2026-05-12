#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
from pathlib import Path

class LlamaCppInstaller:
    def __init__(self):
        self.base_dir = Path("/opt/llamapanel")
        self.llama_dir = self.base_dir / "llama.cpp"
        self.build_dir = self.llama_dir / "build"
        self.log_file = self.base_dir / "logs" / "install.log"
        self.log_file.parent.mkdir(exist_ok=True)
        self._install_running = False
        
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    def run_command(self, cmd, cwd=None):
        self.log(f"执行: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=3600)
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.log(f"  {line}")
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.log(f"  [ERR] {line}")
            if result.returncode != 0:
                raise Exception(f"命令执行失败，返回码: {result.returncode}")
            return result
        except subprocess.TimeoutExpired:
            raise Exception("命令执行超时")
    
    def detect_hardware(self):
        self.log("检测硬件配置...")
        cpu_cores = os.cpu_count()
        self.log(f"CPU 核心数: {cpu_cores}")
        
        has_nvidia = False
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                has_nvidia = True
                self.log("检测到 NVIDIA GPU")
        except FileNotFoundError:
            self.log("未检测到 NVIDIA GPU")
            
        has_amd = False
        try:
            result = subprocess.run(['rocminfo'], capture_output=True, text=True)
            if result.returncode == 0:
                has_amd = True
                self.log("检测到 AMD GPU")
        except FileNotFoundError:
            self.log("未检测到 AMD GPU")
            
        return {
            'cpu_cores': cpu_cores,
            'has_nvidia': has_nvidia,
            'has_amd': has_amd
        }
    
    def clone_llama_cpp(self):
        if self.llama_dir.exists():
            self.log(f"目录已存在: {self.llama_dir}，跳过克隆")
            return
        self.log("开始克隆 llama.cpp...")
        cmd = ['git', 'clone', '--depth', '1', 'https://github.com/ggerganov/llama.cpp.git', str(self.llama_dir)]
        self.run_command(cmd)
        self.log("克隆完成")
    
    def update_llama_cpp(self):
        if not self.llama_dir.exists():
            raise Exception("llama.cpp 未安装，请先执行安装")
        self.log("更新 llama.cpp...")
        cmd = ['git', 'pull']
        self.run_command(cmd, cwd=self.llama_dir)
        self.log("更新完成")
    
    def build_llama_cpp(self):
        self.log("开始编译 llama.cpp...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(exist_ok=True)
        
        hw = self.detect_hardware()
        os.chdir(self.build_dir)
        
        cmake_args = ['cmake', '..']
        if hw['has_nvidia']:
            self.log("启用 CUDA 支持")
            cmake_args.append('-DGGML_CUDA=ON')
        elif hw['has_amd']:
            self.log("启用 ROCm 支持")
            cmake_args.append('-DGGML_HIPBLAS=ON')
        else:
            self.log("使用 CPU 模式（无 GPU 加速）")
        
        self.log(f"CMake 配置: {' '.join(cmake_args)}")
        self.run_command(cmake_args, cwd=self.build_dir)
        
        make_args = ['make', '-j', str(min(hw['cpu_cores'], 8))]
        self.log(f"编译命令: {' '.join(make_args)}")
        self.run_command(make_args, cwd=self.build_dir)
        self.log("编译完成")
        
        server_bin = self.build_dir / 'bin' / 'llama-server'
        if server_bin.exists():
            self.log(f"✅ llama-server 已生成: {server_bin}")
        else:
            self.log("⚠️ 未找到 llama-server")
    
    def clean_build(self):
        self.log("清理编译产物...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
            self.log("清理完成")
        else:
            self.log("build 目录不存在，无需清理")
    
    def rebuild(self):
        self.log("开始重新编译...")
        self.clean_build()
        return self.build_llama_cpp()
    
    def full_install(self):
        self.log("========== 开始完整安装 ==========")
        try:
            self.clone_llama_cpp()
            self.build_llama_cpp()
            self.log("========== 安装完成 ==========")
            return True
        except Exception as e:
            self.log(f"❌ 安装失败: {e}")
            return False
    
    def get_status(self):
        server_bin = self.build_dir / 'bin' / 'llama-server'
        if not server_bin.exists():
            alt_paths = [self.build_dir / 'llama-server', self.llama_dir / 'llama-server']
            for p in alt_paths:
                if p.exists():
                    server_bin = p
                    break
        
        status = {
            'cloned': self.llama_dir.exists(),
            'built': server_bin.exists() if server_bin else False,
            'llama_dir': str(self.llama_dir) if self.llama_dir.exists() else None,
            'server_path': str(server_bin) if server_bin and server_bin.exists() else None
        }
        
        if status['built'] and server_bin:
            try:
                result = subprocess.run([str(server_bin), '--version'], capture_output=True, text=True, timeout=10)
                status['version'] = result.stdout.strip() or result.stderr.strip()
            except:
                status['version'] = 'unknown'
        else:
            status['version'] = 'not built'
        
        return status
