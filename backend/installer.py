#!/usr/bin/env python3
import subprocess
import os
import shutil
import time
import sys
import re
import json
import urllib.request
from pathlib import Path

class LlamaCppInstaller:
    def __init__(self):
        self.base_dir = Path("/opt/llamapanel")
        self.llama_dir = self.base_dir / "llama.cpp"
        self.build_dir = self.llama_dir / "build"
        self.log_file = self.base_dir / "logs" / "install.log"
        self.log_file.parent.mkdir(exist_ok=True)
        self._install_running = False
        self._latest_version = None
        self._last_check_time = 0
        
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
        """执行命令并实时输出日志"""
        full_cmd = self.build_full_cmd(cmd)
        self.log(f"执行: {' '.join(full_cmd)}")
        try:
            process = subprocess.Popen(
                full_cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in process.stdout:
                line = line.rstrip()
                if line.strip():
                    self.log(f"  {line}")
            
            returncode = process.wait()
            
            if check and returncode != 0:
                raise Exception(f"命令执行失败，返回码: {returncode}")
            
            return type('obj', (object,), {'returncode': returncode, 'stdout': '', 'stderr': ''})()
            
        except FileNotFoundError as e:
            raise Exception(f"命令未找到: {full_cmd[0]} - {e}")
    
    def check_command(self, cmd_parts):
        try:
            full_cmd = self.build_full_cmd(cmd_parts)
            subprocess.run(full_cmd, capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def get_latest_stable_tag(self):
        """从 GitHub API 获取最新稳定版本标签"""
        try:
            req = urllib.request.Request(
                'https://api.github.com/repos/ggerganov/llama.cpp/releases/latest',
                headers={'User-Agent': 'LlamaPanel/1.0'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                tag_name = data.get('tag_name', '')
                if tag_name.startswith('v'):
                    tag_name = tag_name[1:]
                self.log(f"获取到最新版本: {tag_name}")
                return tag_name
        except Exception as e:
            self.log(f"获取最新稳定版本失败: {e}")
            return None
    
    def get_current_version(self):
        """获取当前版本号（稳定版标签）"""
        if not self.llama_dir.exists():
            return None
        
        try:
            result = subprocess.run(['git', 'describe', '--tags', '--exact-match'],
                                   cwd=self.llama_dir, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                if version.startswith('v'):
                    version = version[1:]
                return version
        except:
            pass
        
        try:
            result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'],
                                   cwd=self.llama_dir, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                if version.startswith('v'):
                    version = version[1:]
                return version
        except:
            pass
        
        return None
    
    def get_latest_release_version(self):
        return self.get_latest_stable_tag()
    
    def check_for_updates(self):
        """检查是否有新版本可用"""
        current = self.get_current_version()
        if not current:
            return None
        
        latest = self.get_latest_stable_tag()
        
        if current and latest:
            current_num = re.sub(r'[^0-9]', '', current)
            latest_num = re.sub(r'[^0-9]', '', latest)
            return {
                'has_update': current_num != latest_num,
                'current': current,
                'latest': latest
            }
        return None
    
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
        
        ccache_missing = False
        if self.check_command(['ccache', '--version']):
            self.log("✅ ccache 已安装（编译加速）")
        else:
            self.log("⚠️ ccache 未安装，将自动安装以加速后续编译")
            ccache_missing = True
        
        if self.check_command(['nvidia-smi']):
            self.log("✅ NVIDIA CUDA 可用")
        else:
            self.log("⚠️ NVIDIA CUDA 不可用（将使用 CPU 模式）")
        
        if not missing_tools and not ccache_missing:
            self.log("所有依赖已安装")
            return True
        
        if ccache_missing:
            missing_tools.append('ccache')
        
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
                    elif tool == 'ccache':
                        yum_tools.append('ccache')
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
        
        if ccache_missing and not self.check_command(['ccache', '--version']):
            still_missing.append('ccache')
        
        if still_missing:
            self.log(f"⚠️ 以下工具仍不可用: {still_missing}")
            return False
        
        self.log("✅ 所有依赖安装完成")
        if ccache_missing:
            self.log("✅ ccache 已安装，后续编译将自动加速")
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
        
        latest_tag = self.get_latest_stable_tag()
        
        if latest_tag:
            self.log(f"获取到最新稳定版本: {latest_tag}")
            self.log(f"克隆稳定版本 {latest_tag}...")
            cmd = [git_cmd, 'clone', '--branch', latest_tag, '--depth', '1', 
                   'https://github.com/ggerganov/llama.cpp.git', str(self.llama_dir)]
        else:
            self.log("获取稳定版本失败，使用 master 分支")
            cmd = [git_cmd, 'clone', '--depth', '1', 'https://github.com/ggerganov/llama.cpp.git', str(self.llama_dir)]
        
        self.run_command(cmd)
        self.log("克隆完成")
    
    def update_llama_cpp(self):
        if not self.llama_dir.exists():
            raise Exception("llama.cpp 未安装，请先执行安装")
        
        self.log("更新 llama.cpp 到最新稳定版本...")
        git_cmd = self.get_cmd_path('git')
        
        latest_tag = self.get_latest_stable_tag()
        
        if latest_tag:
            current_version = self.get_current_version()
            if current_version == latest_tag:
                self.log(f"当前已是最新稳定版本: {latest_tag}")
                return
            
            self.log(f"发现新版本: {current_version} -> {latest_tag}")
            self.log(f"切换到稳定版本 {latest_tag}...")
            
            self.run_command([git_cmd, 'fetch', '--tags'], cwd=self.llama_dir)
            self.run_command([git_cmd, 'checkout', latest_tag], cwd=self.llama_dir)
            
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
                self.log("已清理旧的编译目录，请重新编译")
        else:
            self.log("获取稳定版本失败，执行 git pull...")
            self.run_command([git_cmd, 'pull'], cwd=self.llama_dir)
        
        self.log("更新完成")
    
    def build_llama_cpp(self):
        self.log("开始编译 llama.cpp...")
        
        if not self.build_dir.exists():
            self.build_dir.mkdir(parents=True, exist_ok=True)
        
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
        
        total_cores = hw['cpu_cores']
        compile_jobs = max(1, total_cores // 2)
        self.log(f"检测到 {total_cores} 核 CPU，使用 {compile_jobs} 线程编译（一半核心数）")
        
        if self.check_command(['ccache', '--version']):
            self.log("✅ 使用 ccache 加速编译")
        
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
        # 重置版本缓存
        self._latest_version = None
        self._last_check_time = 0
        
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
            self.log("清理完成")
        else:
            self.log("build 目录不存在，无需清理")
        
        # 只有在 llama.cpp 目录存在时才重新创建 build 目录
        if self.llama_dir.exists():
            self.build_dir.mkdir(parents=True, exist_ok=True)
            self.log("build 目录已重新创建")
        else:
            self.log("llama.cpp 目录不存在，跳过 build 目录创建")
    
    def rebuild(self):
        self.log("开始重新编译...")
        # 重置版本缓存
        self._latest_version = None
        self._last_check_time = 0
        
        # 检查 llama.cpp 目录是否存在
        if not self.llama_dir.exists():
            self.log("❌ llama.cpp 目录不存在，请先点击「完整安装」")
            return False
        
        self.clean_build()
        self.log("清理完成，开始编译...")
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
    
    def delete_all(self):
        """删除所有 llama.cpp 相关文件"""
        self.log("========== 删除所有 llama.cpp 文件 ==========")
        
        # 重置版本缓存
        self._latest_version = None
        self._last_check_time = 0
        
        if self.llama_dir.exists():
            self.log(f"删除目录: {self.llama_dir}")
            shutil.rmtree(self.llama_dir)
            self.log("✅ llama.cpp 目录已删除")
        else:
            self.log("llama.cpp 目录不存在，跳过")
        
        if self.build_dir.exists():
            self.log(f"删除目录: {self.build_dir}")
            shutil.rmtree(self.build_dir)
            self.log("✅ build 目录已删除")
        
        self.log("========== 删除完成 ==========")
        self.log("请点击「完整安装」重新安装")
    
    def get_status(self):
        # 如果 llama.cpp 目录不存在，返回未克隆状态
        if not self.llama_dir.exists():
            # 重置版本缓存
            self._latest_version = None
            self._last_check_time = 0
            status = {
                'cloned': False,
                'built': False,
                'building': False,
                'building_progress': None,
                'llama_dir': None,
                'server_path': None,
                'version': '❌ 未克隆',
                'has_update': False,
                'latest_version': None
            }
            return status
        
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
        
        current_version = self.get_current_version()
        
        if self._latest_version is None:
            latest = self.get_latest_stable_tag()
            if latest:
                self._latest_version = latest
        
        current_time_val = time.time()
        if current_time_val - self._last_check_time > 86400:
            self._last_check_time = current_time_val
            update_info = self.check_for_updates()
            if update_info:
                self._latest_version = update_info.get('latest')
        
        if is_built:
            if current_version:
                version_text = f"llama.cpp {current_version}"
            else:
                version_text = "✅ 已编译"
            
            has_update = False
            if self._latest_version and current_version:
                current_num = re.sub(r'[^0-9]', '', current_version)
                latest_num = re.sub(r'[^0-9]', '', self._latest_version)
                has_update = current_num != latest_num
            
            status = {
                'cloned': self.llama_dir.exists(),
                'built': True,
                'building': False,
                'building_progress': None,
                'llama_dir': str(self.llama_dir) if self.llama_dir.exists() else None,
                'server_path': str(server_bin) if server_bin else None,
                'version': version_text,
                'has_update': has_update,
                'latest_version': self._latest_version
            }
            return status
        
        is_building = False
        building_progress = None
        
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
            cmake_cache = self.build_dir / 'CMakeCache.txt'
            if cmake_cache.exists():
                is_building = True
                building_progress = "CMake 配置完成，等待编译启动..."
        
        if current_version:
            version_text = f"llama.cpp {current_version} (未编译)"
        else:
            version_text = building_progress if is_building else "❌ 未编译"
        
        status = {
            'cloned': self.llama_dir.exists(),
            'built': False,
            'building': is_building,
            'building_progress': building_progress,
            'llama_dir': str(self.llama_dir) if self.llama_dir.exists() else None,
            'server_path': None,
            'version': version_text,
            'has_update': False,
            'latest_version': self._latest_version
        }
        
        return status