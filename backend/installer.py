#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
import sys
import re
from pathlib import Path

class LlamaCppInstaller:
    def __init__(self):
        self.base_dir = Path("/opt/llamapanel")
        self.llama_dir = self.base_dir / "llama.cpp"
        self.build_dir = self.llama_dir / "build"
        self.log_file = self.base_dir / "logs" / "install.log"
        self.log_file.parent.mkdir(exist_ok=True)
        self._install_running = False
        
        self.cmd_paths = {
            'git': '/usr/bin/git',
            'cmake': '/usr/bin/cmake',
            'make': '/usr/bin/make',
            'g++': '/usr/bin/g++',
            'gcc': '/usr/bin/gcc',
            'python3': '/usr/bin/python3',
            'pip3': '/usr/bin/pip3',
            'nvidia-smi': '/usr/bin/nvidia-smi',
            'apt': '/usr/bin/apt',
            'apt-get': '/usr/bin/apt-get',
        }
        
    def log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
    
    def get_cmd_path(self, cmd_name):
        if cmd_name in self.cmd_paths:
            return self.cmd_paths[cmd_name]
        return cmd_name
    
    def build_full_cmd(self, cmd_parts):
        if not cmd_parts:
            return cmd_parts
        first_cmd = self.get_cmd_path(cmd_parts[0])
        return [first_cmd] + cmd_parts[1:]
    
    def run_command(self, cmd, cwd=None, check=True):
        full_cmd = self.build_full_cmd(cmd)
        self.log(f"执行: {' '.join(full_cmd)}")
        try:
            result = subprocess.run(full_cmd, cwd=cwd, capture_output=True, text=True, timeout=3600)
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
        except FileNotFoundError as e:
            raise Exception(f"命令未找到: {full_cmd[0]} - {e}")
    
    def check_command(self, cmd_parts):
        try:
            full_cmd = self.build_full_cmd(cmd_parts)
            subprocess.run(full_cmd, capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def check_and_install_dependencies(self):
        self.log("========== 检查系统环境 ==========")
        
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
        
        tools = {
            'git': 'git',
            'cmake': 'cmake',
            'make': 'make',
            'g++': 'g++',
            'gcc': 'gcc',
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
        
        if self.check_command(['nvidia-smi']):
            self.log("✅ NVIDIA CUDA 可用")
        else:
            self.log("⚠️ NVIDIA CUDA 不可用（将使用 CPU 模式）")
        
        if not missing_tools:
            self.log("所有依赖已安装")
            return True
        
        self.log(f"需要安装: {', '.join(missing_tools)}")
        
        is_root = (os.geteuid() == 0)
        self.log(f"当前用户: {'root' if is_root else '非root用户'}")
        
        if os_type == "debian":
            self.log("使用 apt 安装依赖...")
            apt_cmd = self.get_cmd_path('apt')
            
            if is_root:
                self.log("检测到 root 用户，直接使用 apt")
                self.run_command([apt_cmd, 'update'], check=False)
                if any(tool in missing_tools for tool in ['gcc', 'g++', 'make']):
                    self.log("检测到缺少编译工具，将安装 build-essential")
                    if 'build-essential' not in missing_tools:
                        missing_tools.append('build-essential')
                install_cmd = [apt_cmd, 'install', '-y'] + missing_tools
            else:
                self.log("检测到非 root 用户，使用 sudo")
                self.run_command(['sudo', apt_cmd, 'update'], check=False)
                if any(tool in missing_tools for tool in ['gcc', 'g++', 'make']):
                    self.log("检测到缺少编译工具，将安装 build-essential")
                    if 'build-essential' not in missing_tools:
                        missing_tools.append('build-essential')
                install_cmd = ['sudo', apt_cmd, 'install', '-y'] + missing_tools
            
            self.run_command(install_cmd)
            
        elif os_type == "redhat":
            self.log("使用 yum 安装依赖...")
            if is_root:
                self.log("检测到 root 用户，直接使用 yum")
                yum_tools = []
                for tool in missing_tools:
                    if tool == 'g++':
                        yum_tools.append('gcc-c++')
                    elif tool == 'gcc':
                        yum_tools.append('gcc')
                    elif tool == 'make':
                        yum_tools.append('make')
                    elif tool == 'cmake':
                        yum_tools.append('cmake')
                    elif tool == 'git':
                        yum_tools.append('git')
                    else:
                        yum_tools.append(tool)
                yum_tools.append('@development-tools')
                install_cmd = ['yum', 'install', '-y'] + list(set(yum_tools))
            else:
                self.log("检测到非 root 用户，使用 sudo")
                install_cmd = ['sudo', 'yum', 'install', '-y'] + missing_tools
            self.run_command(install_cmd)
        
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
            result = subprocess.run([self.get_cmd_path('nvidia-smi')], capture_output=True, text=True)
            if result.returncode == 0:
                has_nvidia = True
                self.log("检测到 NVIDIA GPU")
        except (FileNotFoundError, Exception):
            self.log("未检测到 NVIDIA GPU")
            
        has_amd = False
        try:
            result = subprocess.run(['rocminfo'], capture_output=True, text=True)
            if result.returncode == 0:
                has_amd = True
                self.log("检测到 AMD GPU")
        except (FileNotFoundError, Exception):
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
        git_cmd = self.get_cmd_path('git')
        cmd = [git_cmd, 'clone', '--depth', '1', 'https://github.com/ggerganov/llama.cpp.git', str(self.llama_dir)]
        self.run_command(cmd)
        self.log("克隆完成")
    
    def update_llama_cpp(self):
        if not self.llama_dir.exists():
            raise Exception("llama.cpp 未安装，请先执行安装")
        self.log("更新 llama.cpp...")
        git_cmd = self.get_cmd_path('git')
        cmd = [git_cmd, 'pull']
        self.run_command(cmd, cwd=self.llama_dir)
        self.log("更新完成")
    
    def build_llama_cpp(self):
        self.log("开始编译 llama.cpp...")
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(exist_ok=True)
        
        hw = self.detect_hardware()
        os.chdir(self.build_dir)
        
        cmake_cmd = self.get_cmd_path('cmake')
        make_cmd = self.get_cmd_path('make')
        gcc_cmd = self.get_cmd_path('gcc')
        gpp_cmd = self.get_cmd_path('g++')
        
        cmake_args = [cmake_cmd, '..',
                      f'-DCMAKE_C_COMPILER={gcc_cmd}',
                      f'-DCMAKE_CXX_COMPILER={gpp_cmd}']
        
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
        
        # 智能选择编译线程数：使用一半核心数，但至少1核
        total_cores = hw['cpu_cores']
        compile_jobs = max(1, total_cores // 2)
        self.log(f"检测到 {total_cores} 核 CPU，使用 {compile_jobs} 线程编译（一半核心数）")
        
        make_args = [make_cmd, '-j', str(compile_jobs)]
        self.log(f"编译命令: {' '.join(make_args)}")
        self.run_command(make_args, cwd=self.build_dir)
        self.log("编译完成")
        
        possible_paths = [
            self.build_dir / 'bin' / 'llama-server',
            self.build_dir / 'llama-server',
            self.llama_dir / 'llama-server'
        ]
        
        server_bin = None
        for p in possible_paths:
            if p.exists():
                server_bin = p
                break
        
        if server_bin:
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
            if not self.check_and_install_dependencies():
                self.log("❌ 依赖安装失败，无法继续")
                return False
            self.clone_llama_cpp()
            self.build_llama_cpp()
            self.log("========== 安装完成 ==========")
            return True
        except Exception as e:
            self.log(f"❌ 安装失败: {e}")
            return False
    
    def get_status(self):
        # 检查最终的 server 文件是否存在（编译完成标志）
        server_bin = self.build_dir / 'bin' / 'llama-server'
        if not server_bin.exists():
            alt_paths = [
                self.build_dir / 'llama-server',
                self.llama_dir / 'llama-server'
            ]
            for p in alt_paths:
                if p.exists():
                    server_bin = p
                    break
        
        is_built = server_bin.exists() if server_bin else False
        
        # 如果已编译完成，直接返回
        if is_built:
            status = {
                'cloned': self.llama_dir.exists(),
                'built': True,
                'building': False,
                'building_progress': None,
                'llama_dir': str(self.llama_dir) if self.llama_dir.exists() else None,
                'server_path': str(server_bin) if server_bin else None
            }
            try:
                result = subprocess.run([str(server_bin), '--version'], capture_output=True, text=True, timeout=10)
                version_text = result.stdout.strip() or result.stderr.strip()
                match = re.search(r'version\s+([0-9.]+)', version_text, re.IGNORECASE)
                if match:
                    status['version'] = f"✅ 已编译 (v{match.group(1)})"
                else:
                    status['version'] = "✅ 已编译"
            except:
                status['version'] = "✅ 已编译"
            return status
        
        # 未编译完成，检测编译进程
        is_building = False
        building_progress = None
        
        # 使用 ps 命令检查进程（更可靠）
        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            ps_output = result.stdout
            if 'make' in ps_output and 'llama.cpp' in ps_output:
                is_building = True
                building_progress = "正在编译中 (make 进程运行中)..."
            elif 'cc1plus' in ps_output or 'g++' in ps_output:
                is_building = True
                building_progress = "正在编译中 (编译器进程运行中)..."
        except:
            pass
        
        # 获取编译进度
        if is_building:
            try:
                obj_dir = self.build_dir / 'src' / 'CMakeFiles' / 'llama.dir'
                if obj_dir.exists():
                    obj_count = len(list(obj_dir.glob('*.o')))
                    if obj_count > 0:
                        building_progress = f"正在编译中... (已编译 {obj_count} 个文件)"
            except:
                pass
        else:
            # 没有进程在运行，检查 CMake 配置状态
            cmake_cache = self.build_dir / 'CMakeCache.txt'
            if cmake_cache.exists():
                is_building = True
                building_progress = "CMake 配置完成，等待编译启动..."
        
        status = {
            'cloned': self.llama_dir.exists(),
            'built': False,
            'building': is_building,
            'building_progress': building_progress,
            'llama_dir': str(self.llama_dir) if self.llama_dir.exists() else None,
            'server_path': None
        }
        
        if is_building:
            status['version'] = building_progress or "⏳ 编译中..."
        else:
            status['version'] = "❌ 未编译"
        
        return status