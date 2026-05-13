#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
import sys
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
    
    def run_command(self, cmd, cwd=None, check=True):
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
            if check and result.returncode != 0:
                raise Exception(f"命令执行失败，返回码: {result.returncode}")
            return result
        except subprocess.TimeoutExpired:
            raise Exception("命令执行超时")
    
    def check_command(self, cmd):
        """检查命令是否存在"""
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def check_and_install_dependencies(self):
        """检查并安装系统依赖"""
        self.log("========== 检查系统环境 ==========")
        
        # 检测操作系统
        os_type = "unknown"
        if os.path.exists("/etc/debian_version"):
            os_type = "debian"
            self.log("检测到 Debian/Ubuntu 系统")
        elif os.path.exists("/etc/redhat-release"):
            os_type = "redhat"
            self.log("检测到 CentOS/RHEL 系统")
        else:
            self.log("未知操作系统，跳过依赖安装")
            return True
        
        # 需要检查的工具列表
        tools = {
            'git': 'git',
            'cmake': 'cmake',
            'make': 'make',
            'g++': 'g++',
            'python3': 'python3',
            'pip3': 'python3-pip'
        }
        
        missing_tools = []
        for tool, package in tools.items():
            if self.check_command([tool, '--version']):
                self.log(f"✅ {tool} 已安装")
            else:
                self.log(f"❌ {tool} 未安装")
                missing_tools.append(package)
        
        # CUDA 检查（可选）
        if self.check_command(['nvidia-smi']):
            self.log("✅ NVIDIA CUDA 可用")
        else:
            self.log("⚠️ NVIDIA CUDA 不可用（将使用 CPU 模式）")
        
        if not missing_tools:
            self.log("所有依赖已安装")
            return True
        
        # 安装缺失的依赖
        self.log(f"需要安装: {', '.join(missing_tools)}")
        
        # 检测是否为 root 用户
        is_root = (os.geteuid() == 0)
        self.log(f"当前用户: {'root' if is_root else '非root用户'}")
        
        if os_type == "debian":
            # Ubuntu/Debian 系统
            self.log("使用 apt 安装依赖...")
            
            if is_root:
                # root 用户，直接使用 apt
                self.log("检测到 root 用户，直接使用 apt")
                self.run_command(['apt', 'update'], check=False)
                install_cmd = ['apt', 'install', '-y'] + missing_tools
            else:
                # 非 root 用户，使用 sudo
                self.log("检测到非 root 用户，使用 sudo")
                self.run_command(['sudo', 'apt', 'update'], check=False)
                install_cmd = ['sudo', 'apt', 'install', '-y'] + missing_tools
            
            self.run_command(install_cmd)
            
        elif os_type == "redhat":
            # CentOS/RHEL 系统
            self.log("使用 yum 安装依赖...")
            
            if is_root:
                # root 用户，直接使用 yum
                self.log("检测到 root 用户，直接使用 yum")
                install_cmd = ['yum', 'install', '-y'] + missing_tools
            else:
                # 非 root 用户，使用 sudo
                self.log("检测到非 root 用户，使用 sudo")
                install_cmd = ['sudo', 'yum', 'install', '-y'] + missing_tools
            
            self.run_command(install_cmd)
        
        # 验证安装结果
        still_missing = []
        for tool, package in tools.items():
            if not self.check_command([tool, '--version']):
                still_missing.append(tool)
        
        if still_missing:
            self.log(f"⚠️ 以下工具仍不可用: {still_missing}")
            return False
        
        self.log("✅ 所有依赖安装完成")
        return True
    
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
            # 第一步：检查并安装依赖
            if not self.check_and_install_dependencies():
                self.log("❌ 依赖安装失败，无法继续")
                return False
            
            # 第二步：克隆代码
            self.clone_llama_cpp()
            
            # 第三步：编译
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