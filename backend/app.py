#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from pathlib import Path
import sys
import subprocess
import os
import time
import threading

# 动态获取 backend 目录路径，支持本地开发和服务器部署
sys.path.append(str(Path(__file__).parent))
from installer import LlamaCppInstaller
from routers import download_router, local_router, progress_router, system_router, server_router, set_model_manager
from model_manager import ModelManager
from config import PROJECT_DIR, LOGS_DIR, ensure_dirs

app = FastAPI(title="LlamaPanel", description="llama.cpp 管理面板")
installer = LlamaCppInstaller()

# 创建全局单例 ModelManager 并设置到路由模块
model_manager = ModelManager()
set_model_manager(model_manager)

# 注册路由
app.include_router(download_router)
app.include_router(local_router)
app.include_router(progress_router)
app.include_router(system_router)
app.include_router(server_router)

# ==================== LlamaPanel 更新状态跟踪 ====================
_update_panel_status = {
    "running": False,
    "success": None,
    "message": "",
    "started_at": None,
    "finished_at": None,
}
_update_panel_lock = threading.Lock()

def _set_update_status(running=None, success=None, message=None):
    """线程安全地更新面板状态"""
    with _update_panel_lock:
        if running is not None:
            _update_panel_status["running"] = running
        if success is not None:
            _update_panel_status["success"] = success
        if message is not None:
            _update_panel_status["message"] = message

# 更新 LlamaPanel 的函数
def update_llamapanel():
    """更新 LlamaPanel 自身（增强版：状态跟踪 + 更好错误处理）"""
    log_file = LOGS_DIR / "update.log"
    log_file.parent.mkdir(exist_ok=True)
    
    def log_msg(msg):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        print(log_msg)
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except PermissionError:
            # 如果日志文件权限不足，尝试修复目录权限
            try:
                os.chmod(log_file.parent, 0o755)
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(log_msg + '\n')
            except:
                print(f"[{timestamp}] ⚠️ 无法写入日志文件（权限不足），但更新仍会继续")
    
    try:
        _set_update_status(running=True, success=None, message="正在更新...")
        log_msg("========== 开始更新 LlamaPanel ==========")
        
        repo_path = str(PROJECT_DIR)
        
        log_msg(f"当前工作目录: {os.getcwd()}")
        log_msg(f"项目目录: {repo_path}")
        
        # 检查 git 是否可用
        try:
            git_check = subprocess.run(['git', '--version'], capture_output=True, text=True, timeout=10)
            if git_check.returncode != 0:
                log_msg("❌ git 命令不可用，请先安装 git")
                _set_update_status(running=False, success=False, message="git 命令不可用")
                return False
            log_msg(f"git 版本: {git_check.stdout.strip()}")
        except FileNotFoundError:
            log_msg("❌ git 未安装，无法更新")
            _set_update_status(running=False, success=False, message="git 未安装，请先安装 git")
            return False
        
        # 检查是否为 git 仓库
        git_check_dir = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        if git_check_dir.returncode != 0:
            log_msg("❌ 项目目录不是一个 git 仓库，无法通过 git 更新")
            log_msg("请手动从 GitHub 克隆: git clone https://github.com/CHENBIN-1979/llamapanel.git")
            _set_update_status(running=False, success=False, message="不是 git 仓库，请手动克隆")
            return False
        
        # 获取 git 目录的实际路径
        git_dir_raw = git_check_dir.stdout.strip()
        if not os.path.isabs(git_dir_raw):
            git_dir_real = os.path.normpath(os.path.join(repo_path, git_dir_raw))
        else:
            git_dir_real = git_dir_raw
        log_msg(f"git 目录: {git_dir_real}")
        
        # === 关键修复：用实际写文件测试检查和修复 .git 目录权限 ===
        # os.access() 在某些系统上可能返回假阳性（说可写但实际写不了），
        # 所以这里用实际创建临时文件来验证，确保 git 操作不会卡在 Permission denied
        try:
            if os.path.isdir(git_dir_real):
                test_file = os.path.join(git_dir_real, ".write_test_llamapanel")
                git_writable = True
                try:
                    with open(test_file, 'w', encoding='utf-8') as f:
                        f.write("test")
                    os.remove(test_file)
                except (PermissionError, OSError):
                    git_writable = False
                
                if git_writable:
                    log_msg("✅ .git 目录可正常写入")
                else:
                    log_msg("⚠️ 检测到 .git 目录权限不足（Web 用户无法写入文件）")
                    log_msg("正在自动修复权限...")
                    
                    perm_fixed = False
                    
                    # 方案一：chmod -R u+w .git（最可靠的方式，从外部修改权限）
                    for fix_cmd in [
                        ['chmod', '-R', 'u+w', git_dir_real],
                        ['chmod', '-R', '755', git_dir_real],
                    ]:
                        try:
                            fix_result = subprocess.run(
                                fix_cmd,
                                capture_output=True, text=True, timeout=30
                            )
                            if fix_result.returncode == 0:
                                log_msg(f"✅ 通过 chmod 修复权限成功")
                                perm_fixed = True
                                break
                        except:
                            pass
                    
                    # 方案二：如果直接 chmod 不行，尝试 sudo -n chmod
                    if not perm_fixed:
                        log_msg("尝试通过 sudo 修复权限...")
                        for fix_cmd in [
                            ['sudo', '-n', 'chmod', '-R', 'u+w', git_dir_real],
                            ['sudo', '-n', 'chmod', '-R', '777', git_dir_real],
                        ]:
                            try:
                                sudo_result = subprocess.run(
                                    fix_cmd,
                                    capture_output=True, text=True, timeout=30
                                )
                                if sudo_result.returncode == 0:
                                    log_msg("✅ 通过 sudo chmod 修复权限成功")
                                    perm_fixed = True
                                    break
                                else:
                                    log_msg(f"sudo 修复失败（{sudo_result.stderr.strip()}），可能未配置 NOPASSWD")
                            except:
                                log_msg("sudo 不可用")
                    
                    # 方案三：尝试 Python os.chmod 递归修复
                    if not perm_fixed:
                        log_msg("尝试通过 Python os.chmod 递归修复...")
                        try:
                            for root_dir, dirs, files in os.walk(git_dir_real):
                                for name in dirs + files:
                                    try:
                                        os.chmod(os.path.join(root_dir, name), 0o777)
                                    except:
                                        pass
                            # 再次验证
                            try:
                                with open(test_file, 'w', encoding='utf-8') as f:
                                    f.write("test")
                                os.remove(test_file)
                                perm_fixed = True
                            except:
                                pass
                        except:
                            pass
                    
                    if perm_fixed:
                        log_msg("✅ .git 目录权限修复成功")
                    else:
                        log_msg("⚠️ .git 目录权限修复失败，尝试继续更新...")
                        log_msg("💡 如需手动修复，请在服务器执行：")
                        log_msg(f"   sudo chown -R $(whoami):$(whoami) {git_dir_real}")
                        log_msg(f"   或: sudo chmod -R 777 {git_dir_real}")
        except Exception as perm_e:
            log_msg(f"⚠️ 检查和修复 .git 权限时出现异常（不影响更新）: {perm_e}")
        
        # 获取远程仓库地址
        remote_result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        if remote_result.returncode == 0:
            log_msg(f"远程仓库: {remote_result.stdout.strip()}")
        
        # === 步骤1: 先暂存本地修改，防止 git pull 因冲突失败 ===
        log_msg("暂存本地修改...")
        stash_result = subprocess.run(
            ['git', 'stash', 'push', '-m', 'llamapanel_update_auto_stash'],
            cwd=repo_path, capture_output=True, text=True, timeout=30
        )
        had_local_changes = (stash_result.returncode == 0 and
                            "No local changes" not in stash_result.stdout and
                            "No local changes" not in stash_result.stderr)
        if had_local_changes:
            log_msg("✅ 已暂存本地修改，pull 完成后将自动恢复")
        
        # === 步骤2: 尝试 git pull（带权限修复重试逻辑）===
        def _run_git_pull():
            """执行一次 git pull，返回 (result, already_uptodate)"""
            log_msg("执行: git pull")
            r = subprocess.run(
                ['git', 'pull'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            log_msg(f"git pull 返回码: {r.returncode}")
            if r.stdout:
                log_msg(f"输出: {r.stdout}")
            if r.stderr:
                log_msg(f"错误: {r.stderr}")
            
            up_to_date = r.stdout and "Already up to date" in r.stdout
            if up_to_date:
                log_msg("✅ 已是最新版本")
            return r, up_to_date
        
        result, already_uptodate = _run_git_pull()
        
        # 如果 pull 因权限问题失败，修复权限后重试一次
        if result.returncode != 0 and not already_uptodate:
            if "Permission denied" in (result.stderr or ""):
                log_msg("🔧 git pull 因权限问题失败，尝试修复权限后重试...")
                # 尝试修复 .git 下的所有文件和目录权限
                try:
                    subprocess.run(
                        ['chmod', '-R', 'u+w', git_dir_real],
                        capture_output=True, text=True, timeout=30
                    )
                    log_msg("已执行 chmod -R u+w .git，准备重试 git pull")
                except:
                    try:
                        subprocess.run(
                            ['sudo', '-n', 'chmod', '-R', '777', git_dir_real],
                            capture_output=True, text=True, timeout=30
                        )
                        log_msg("已执行 sudo chmod -R 777 .git，准备重试 git pull")
                    except:
                        log_msg("权限修复失败，继续尝试 fetch + reset 降级方案")
                
                # 重试 pull
                result, already_uptodate = _run_git_pull()
        
        if result.returncode != 0 and not already_uptodate:
            # === 步骤3: pull 失败时，使用 fetch + reset --hard 降级 ===
            log_msg("git pull 失败，尝试 git fetch + reset --hard 降级方案")
            
            # 获取当前分支名
            branch_result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=repo_path, capture_output=True, text=True, timeout=10
            )
            current_branch = branch_result.stdout.strip() or 'main'
            log_msg(f"当前分支: {current_branch}")
            
            log_msg("执行: git fetch origin")
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            log_msg(f"git fetch 返回码: {fetch_result.returncode}")
            if fetch_result.stdout:
                log_msg(f"fetch 输出: {fetch_result.stdout}")
            if fetch_result.stderr:
                log_msg(f"fetch 错误: {fetch_result.stderr}")
            if fetch_result.returncode != 0:
                # 如果 fetch 因权限问题失败，修复权限后重试一次
                if "Permission denied" in (fetch_result.stderr or ""):
                    log_msg("🔧 git fetch 因权限问题失败，尝试修复权限后重试...")
                    try:
                        subprocess.run(
                            ['chmod', '-R', 'u+w', git_dir_real],
                            capture_output=True, text=True, timeout=30
                        )
                        log_msg("已执行 chmod -R u+w .git，准备重试 git fetch")
                    except:
                        try:
                            subprocess.run(
                                ['sudo', '-n', 'chmod', '-R', '777', git_dir_real],
                                capture_output=True, text=True, timeout=30
                            )
                            log_msg("已执行 sudo chmod -R 777 .git，准备重试 git fetch")
                        except:
                            log_msg("权限修复失败")
                    
                    # 重试 fetch
                    log_msg("重试: git fetch origin")
                    fetch_result = subprocess.run(
                        ['git', 'fetch', 'origin'],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    log_msg(f"git fetch 重试返回码: {fetch_result.returncode}")
                    if fetch_result.stdout:
                        log_msg(f"fetch 输出: {fetch_result.stdout}")
                    if fetch_result.stderr:
                        log_msg(f"fetch 错误: {fetch_result.stderr}")
                
                if fetch_result.returncode != 0:
                    log_msg("❌ git fetch 最终失败，网络可能不通或权限仍不足")
                    _set_update_status(running=False, success=False, message="网络连接失败，无法获取更新")
                    return False
            else:
                # fetch 成功后先检查是否有新提交
                log_msg("检查远程是否有新提交...")
                log_result = subprocess.run(
                    ['git', 'log', f'HEAD..origin/{current_branch}', '--oneline'],
                    cwd=repo_path, capture_output=True, text=True, timeout=10
                )
                if log_result.stdout.strip():
                    new_commits = len(log_result.stdout.strip().split('\n'))
                    log_msg(f"发现 {new_commits} 个新提交")
                    # 强制重置到远程分支
                    reset_result = subprocess.run(
                        ['git', 'reset', '--hard', f'origin/{current_branch}'],
                        cwd=repo_path, capture_output=True, text=True, timeout=30
                    )
                    log_msg(f"git reset 返回码: {reset_result.returncode}")
                    if reset_result.stdout:
                        log_msg(f"reset 输出: {reset_result.stdout.strip()}")
                    if reset_result.returncode == 0:
                        log_msg("✅ 已强制同步到远程最新代码")
                    else:
                        log_msg("❌ git reset 失败")
                        _set_update_status(running=False, success=False, message="git reset 失败")
                        return False
                else:
                    already_uptodate = True
                    log_msg("✅ 远程无新提交，已是最新版本")
        
        # 恢复之前暂存的本地修改
        if had_local_changes:
            log_msg("恢复本地暂存的修改...")
            pop_result = subprocess.run(
                ['git', 'stash', 'pop'],
                cwd=repo_path, capture_output=True, text=True, timeout=30
            )
            if pop_result.returncode == 0:
                log_msg("✅ 本地修改已恢复")
            else:
                log_msg("⚠️ 本地修改自动恢复失败，请手动执行: git stash pop")
        
        if already_uptodate:
            log_msg("✅ LlamaPanel 已经是最新版本，无需更新")
            _set_update_status(running=False, success=True, message="已经是最新版本")
            return True
        
        log_msg("✅ 代码更新完成")
        
        # === 步骤4: 安装 Python 依赖 ===
        requirements_file = PROJECT_DIR / "requirements.txt"
        if requirements_file.exists():
            log_msg("检查 Python 依赖...")
            # 尝试多个可能的 pip 路径
            pip_candidates = [
                str(PROJECT_DIR / "venv/bin/pip"),
                str(PROJECT_DIR / ".venv/bin/pip"),
                'pip3',
                'pip',
            ]
            pip_cmd = None
            for candidate in pip_candidates:
                try:
                    test = subprocess.run([candidate, '--version'], capture_output=True, text=True, timeout=10)
                    if test.returncode == 0:
                        pip_cmd = candidate
                        log_msg(f"使用 pip: {candidate} ({test.stdout.strip()})")
                        break
                except:
                    continue
            
            if pip_cmd:
                pip_result = subprocess.run(
                    [pip_cmd, 'install', '-r', 'requirements.txt'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                log_msg(f"pip 安装返回码: {pip_result.returncode}")
                if pip_result.returncode != 0:
                    log_msg(f"pip 安装输出: {pip_result.stdout[:500] if pip_result.stdout else ''}")
                    log_msg(f"pip 安装错误: {pip_result.stderr[:500] if pip_result.stderr else ''}")
                    log_msg("⚠️ Python 依赖安装有警告，但不影响核心功能")
            else:
                log_msg("⚠️ 未找到 pip，跳过 Python 依赖安装")
        
        # === 步骤5: 尝试重启服务 ===
        log_msg("尝试重启 LlamaPanel 服务...")
        restart_methods = [
            (['sudo', '-n', 'systemctl', 'restart', 'llamapanel'], "systemctl"),
            (['sudo', '-n', 'supervisorctl', 'restart', 'llamapanel'], "supervisorctl"),
        ]
        
        restart_success = False
        for cmd, method in restart_methods:
            try:
                restart_result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )
                log_msg(f"{method} 重启返回码: {restart_result.returncode}")
                if restart_result.returncode == 0:
                    log_msg(f"✅ 服务已通过 {method} 重启")
                    restart_success = True
                    break
            except:
                continue
        
        if not restart_success:
            log_msg("⚠️ 自动重启服务失败，可能需要手动操作")
            log_msg("请在 SSH 中执行: sudo systemctl restart llamapanel")
            log_msg("或等待下次服务自动重启时生效")
        
        log_msg("========== 更新完成 ==========")
        _set_update_status(running=False, success=True, message="更新完成，请稍后刷新页面")
        return True
    except Exception as e:
        log_msg(f"更新失败: {e}")
        import traceback
        log_msg(traceback.format_exc())
        _set_update_status(running=False, success=False, message=f"更新失败: {str(e)}")
        return False

HTML_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>LlamaPanel - llama.cpp 管理面板</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .nav-bar {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .nav-bar a {
            color: white;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 8px;
            background: rgba(255,255,255,0.2);
            transition: all 0.3s;
            cursor: pointer;
        }
        .nav-bar a:hover {
            background: rgba(255,255,255,0.3);
        }
        .nav-bar a.active {
            background: white;
            color: #667eea;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }
        h1 { color: #333; margin-bottom: 8px; }
        .subtitle { color: #666; margin-bottom: 24px; }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-ok { background: #d4edda; color: #155724; }
        .status-warning { background: #fff3cd; color: #856404; }
        .status-building { background: #cce5ff; color: #004085; }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            margin-right: 10px;
            margin-bottom: 10px;
            transition: all 0.3s;
        }
        button:hover { background: #5a67d8; transform: translateY(-1px); }
        button.danger { background: #e53e3e; }
        button.danger:hover { background: #c53030; }
        button.success { background: #38a169; }
        button.success:hover { background: #2f855a; }
        button:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
        .log-viewer {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            padding: 16px;
            border-radius: 8px;
            height: 400px;
            overflow-y: auto;
            font-size: 12px;
        }
        .log-line {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            padding: 3px 5px;
            border-bottom: 1px solid #2a2a2a;
            white-space: pre-wrap;
            word-break: break-all;
            margin: 0;
        }
        .log-empty {
            height: 5px;
            border-bottom: none;
        }
        .log-error {
            color: #ff6b6b;
            background-color: rgba(255, 107, 107, 0.1);
        }
        .log-warning {
            color: #ffd93d;
        }
        .log-success {
            color: #6bcb77;
        }
        .log-command {
            color: #4d9de0;
        }
        .log-separator {
            color: #c9c9c9;
            font-weight: bold;
            border-bottom: 1px solid #555;
            margin: 5px 0;
            background-color: #2a2a2a;
        }
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }
        .info-item {
            background: #f7fafc;
            padding: 12px;
            border-radius: 8px;
        }
        .info-label { font-size: 12px; color: #718096; margin-bottom: 4px; }
        .info-value { font-size: 16px; font-weight: 600; color: #2d3748; word-break: break-all; }
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #e2e8f0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .log-controls { margin-bottom: 10px; display: flex; gap: 10px; align-items: center; }
        .auto-refresh { font-size: 12px; color: #666; display: flex; align-items: center; gap: 5px; }
        hr { margin: 15px 0; border: none; border-top: 1px solid #e2e8f0; }
        
        .log-viewer::-webkit-scrollbar {
            width: 8px;
        }
        .log-viewer::-webkit-scrollbar-track {
            background: #1e1e1e;
            border-radius: 4px;
        }
        .log-viewer::-webkit-scrollbar-thumb {
            background: #555;
            border-radius: 4px;
        }
        .log-viewer::-webkit-scrollbar-thumb:hover {
            background: #777;
        }
        .page-content {
            transition: opacity 0.3s ease;
        }
        .hidden {
            display: none;
        }
        .button-group {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 10px;
        }
        /* ==================== 更新日志模态框 ==================== */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            backdrop-filter: blur(4px);
        }
        .modal-overlay.active {
            display: flex;
        }
        .modal-box {
            background: white;
            border-radius: 16px;
            padding: 24px;
            width: 90%;
            max-width: 900px;
            max-height: 85vh;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            animation: modalIn 0.3s ease;
        }
        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.95) translateY(-10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-shrink: 0;
        }
        .modal-header h2 {
            font-size: 18px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .modal-header .modal-status {
            font-size: 13px;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 500;
        }
        .modal-status-running {
            background: #cce5ff;
            color: #004085;
        }
        .modal-status-success {
            background: #d4edda;
            color: #155724;
        }
        .modal-status-fail {
            background: #f8d7da;
            color: #721c24;
        }
        .modal-close-btn {
            background: #e2e8f0;
            color: #4a5568;
            border: none;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }
        .modal-close-btn:hover {
            background: #cbd5e0;
            transform: none;
        }
        .modal-body {
            flex: 1;
            overflow-y: auto;
            min-height: 200px;
        }
        .modal-footer {
            flex-shrink: 0;
            padding-top: 12px;
            margin-top: 12px;
            border-top: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 13px;
            color: #718096;
        }
        .modal-footer .spinner {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid #e2e8f0;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.6s linear infinite;
            margin-right: 6px;
            vertical-align: middle;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav-bar">
            <a onclick="showPage('home')" id="navHome" class="active">🏠 主页</a>
            <a onclick="showPage('download')" id="navDownload">📥 模型下载</a>
            <a onclick="showPage('local')" id="navLocal">💾 本地模型</a>
            <a onclick="showPage('system')" id="navSystem">📋 系统信息</a>
            <a onclick="showPage('server')" id="navServer">🚀 服务器配置</a>
        </div>
        
        <!-- 主页内容 -->
        <div id="homePage" class="page-content">
            <div class="card">
                <h1>🦙 LlamaPanel</h1>
                <p class="subtitle">llama.cpp 图形化管理面板 - 无需命令行</p>
                
                <div class="button-group">
                    <button onclick="installLlama()" id="installBtn">🚀 完整安装 llama.cpp</button>
                    <button onclick="updateLlama()" id="updateBtn">🔄 更新llama.cpp</button>
                    <button onclick="rebuildLlama()" id="rebuildBtn">🔨 重新编译</button>
                    <button onclick="cleanBuild()" class="danger" id="cleanBtn">🧹 清理编译</button>
                    <button onclick="deleteAll()" class="danger" id="deleteBtn">🗑️ 删除所有</button>
                    <button onclick="updateLlamaPanel()" class="success" id="updatePanelBtn">🔄 更新 LlamaPanel</button>
                </div>
            </div>
            
            <div class="card">
                <h2>📊 安装状态</h2>
                <div id="statusInfo">
                    <div class="loading"></div> 加载中...
                </div>
            </div>
            
            <div class="card">
                <h2>📋 安装日志</h2>
                <div class="log-controls">
                    <button onclick="refreshLog()" style="margin-bottom: 0;">🔄 刷新</button>
                    <label class="auto-refresh">
                        <input type="checkbox" id="autoRefresh"> 自动刷新 (2秒)
                    </label>
                </div>
                <div id="logContent" class="log-viewer">
                    加载日志中...
                </div>
            </div>
        </div>
        
        <!-- LlamaPanel 更新日志模态框 -->
        <div id="updateModal" class="modal-overlay">
            <div class="modal-box">
                <div class="modal-header">
                    <h2>
                        <span>🔄 LlamaPanel 更新</span>
                        <span id="updateModalStatus" class="modal-status modal-status-running">更新中...</span>
                    </h2>
                    <button class="modal-close-btn" onclick="closeUpdateModal()" id="updateModalCloseBtn" disabled title="更新完成后可关闭">✕</button>
                </div>
                <div id="updateModalBody" class="modal-body log-viewer" style="height: auto; min-height: 300px; max-height: 55vh;">
                    <div class="log-line">等待更新任务启动...</div>
                </div>
                <div class="modal-footer">
                    <span id="updateModalFooter">
                        <span class="spinner"></span> 更新执行中，请勿关闭此窗口...
                    </span>
                    <span id="updateModalTime">等待中</span>
                </div>
            </div>
        </div>

        <!-- 模型下载页面容器 -->
        <div id="downloadPage" class="page-content hidden">
            <iframe src="/api/download/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
        
        <!-- 本地模型页面容器 -->
        <div id="localPage" class="page-content hidden">
            <iframe src="/api/local/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
        
        <!-- 系统信息页面容器 -->
        <div id="systemPage" class="page-content hidden">
            <iframe src="/api/system/page" style="width: 100%; min-height: 600px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
        
        <!-- 服务器配置页面容器 -->
        <div id="serverPage" class="page-content hidden">
            <iframe src="/api/server/page" style="width: 100%; min-height: 800px; border: none; border-radius: 16px; background: white;"></iframe>
        </div>
    </div>
    
    <script>
        let autoRefreshInterval = null;
        let statusInterval = null;
        
        // 页面切换函数
        function showPage(page) {
            const homePage = document.getElementById('homePage');
            const downloadPage = document.getElementById('downloadPage');
            const localPage = document.getElementById('localPage');
            const systemPage = document.getElementById('systemPage');
            const serverPage = document.getElementById('serverPage');
            const navHome = document.getElementById('navHome');
            const navDownload = document.getElementById('navDownload');
            const navLocal = document.getElementById('navLocal');
            const navSystem = document.getElementById('navSystem');
            const navServer = document.getElementById('navServer');
            
            // 隐藏所有页面
            homePage.classList.add('hidden');
            downloadPage.classList.add('hidden');
            localPage.classList.add('hidden');
            systemPage.classList.add('hidden');
            serverPage.classList.add('hidden');
            
            // 移除所有 active 状态
            navHome.classList.remove('active');
            navDownload.classList.remove('active');
            navLocal.classList.remove('active');
            navSystem.classList.remove('active');
            navServer.classList.remove('active');
            
            if (page === 'home') {
                homePage.classList.remove('hidden');
                navHome.classList.add('active');
                refreshStatus();
                refreshLog();
            } else if (page === 'download') {
                downloadPage.classList.remove('hidden');
                navDownload.classList.add('active');
                const iframe = document.querySelector('#downloadPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            } else if (page === 'local') {
                localPage.classList.remove('hidden');
                navLocal.classList.add('active');
                const iframe = document.querySelector('#localPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            } else if (page === 'system') {
                systemPage.classList.remove('hidden');
                navSystem.classList.add('active');
                const iframe = document.querySelector('#systemPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            } else if (page === 'server') {
                serverPage.classList.remove('hidden');
                navServer.classList.add('active');
                const iframe = document.querySelector('#serverPage iframe');
                if (iframe) {
                    iframe.contentWindow.location.reload();
                }
            }
        }
        
        function startAutoRefresh() {
            if (autoRefreshInterval) clearInterval(autoRefreshInterval);
            autoRefreshInterval = setInterval(() => {
                const chk = document.getElementById('autoRefresh');
                if (chk && chk.checked === true) {
                    refreshLog();
                }
            }, 2000);
        }
        
        function bindAutoRefreshCheckbox() {
            const chk = document.getElementById('autoRefresh');
            if (chk) {
                chk.addEventListener('change', function() {
                    if (this.checked) {
                        if (autoRefreshInterval) clearInterval(autoRefreshInterval);
                        autoRefreshInterval = setInterval(() => {
                            const c = document.getElementById('autoRefresh');
                            if (c && c.checked === true) {
                                refreshLog();
                            }
                        }, 2000);
                    } else {
                        if (autoRefreshInterval) {
                            clearInterval(autoRefreshInterval);
                            autoRefreshInterval = null;
                        }
                    }
                });
            }
        }
        
        async function fetchAPI(endpoint, method='GET', data=null) {
            const options = { method: method };
            if (data && method === 'POST') {
                options.headers = { 'Content-Type': 'application/json' };
                options.body = JSON.stringify(data);
            }
            const response = await fetch(endpoint, options);
            return await response.json();
        }
        
        async function refreshStatus() {
            try {
                const status = await fetchAPI('/api/status');
                const info = document.getElementById('statusInfo');
                if (!info) return;
                
                let buildStatusHtml = '';
                let buildStatusClass = '';
                
                if (status.built) {
                    buildStatusHtml = '✅ 已编译';
                    buildStatusClass = 'status-ok';
                } else if (status.building) {
                    buildStatusHtml = '⏳ ' + (status.building_progress || '编译中...');
                    buildStatusClass = 'status-building';
                } else {
                    buildStatusHtml = '❌ 未编译';
                    buildStatusClass = 'status-warning';
                }
                
                let currentVersionText = status.version || '未知';
                let latestVersionHtml = '';
                
                if (status.has_update && status.latest_version) {
                    latestVersionHtml = `<div class="info-value" style="color: #e53e3e; font-size: 14px; margin-top: 5px;">
                                            ⚠️ 最新版本: ${status.latest_version} (点击「更新版本」)
                                        </div>`;
                } else if (status.latest_version) {
                    latestVersionHtml = `<div class="info-value" style="color: #6bcb77; font-size: 14px; margin-top: 5px;">
                                            ✅ 已是最新版本: ${status.latest_version}
                                        </div>`;
                } else {
                    latestVersionHtml = `<div class="info-value" style="color: #888; font-size: 14px; margin-top: 5px;">
                                            📡 正在检查更新...
                                        </div>`;
                }
                
                info.innerHTML = `
                    <div class="info-grid">
                        <div class="info-item">
                            <div class="info-label">克隆状态</div>
                            <div class="info-value">${status.cloned ? '✅ 已克隆' : '❌ 未克隆'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">编译状态</div>
                            <div class="info-value"><span class="status-badge ${buildStatusClass}">${buildStatusHtml}</span></div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">llama.cpp 路径</div>
                            <div class="info-value">${status.llama_dir || '未设置'}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">llama-server 路径</div>
                            <div class="info-value">${status.server_path || (status.building ? '⏳ 编译中...' : '未编译')}</div>
                        </div>
                        <div class="info-item">
                            <div class="info-label">当前版本</div>
                            <div class="info-value">${currentVersionText}</div>
                            <div class="info-label" style="margin-top: 8px;">最新版本</div>
                            ${latestVersionHtml}
                        </div>
                    </div>
                `;
            } catch(e) {
                console.error('刷新状态失败:', e);
            }
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function refreshLog() {
            try {
                const response = await fetch('/api/log');
                let text = await response.text();
                const logDiv = document.getElementById('logContent');
                if (!logDiv) return;
                
                if (!text || text === '暂无日志' || text.trim() === '') {
                    logDiv.innerHTML = '<div class="log-line">暂无日志，请点击"完整安装"开始安装</div>';
                    return;
                }
                
                let processed = text.replace(/\\\\n/g, '\\n');
                processed = processed.replace(/\\\\r\\\\n/g, '\\n');
                
                const lines = processed.split('\\n');
                
                let html = '';
                for (let i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (line.trim() === '') continue;
                    
                    let lineClass = 'log-line';
                    let displayLine = escapeHtml(line);
                    
                    if (line.includes('[ERR]') || line.includes('error') || line.includes('Error')) {
                        lineClass += ' log-error';
                        displayLine = '❌ ' + displayLine;
                    } else if (line.includes('✅')) {
                        lineClass += ' log-success';
                    } else if (line.includes('⚠️') || line.includes('Warning')) {
                        lineClass += ' log-warning';
                        displayLine = '⚠️ ' + displayLine;
                    } else if (line.includes('执行:')) {
                        lineClass += ' log-command';
                        displayLine = '🔧 ' + displayLine;
                    } else if (line.includes('==========')) {
                        lineClass += ' log-separator';
                    } else if (line.includes('完成') || line.includes('成功')) {
                        lineClass += ' log-success';
                    }
                    
                    html += `<div class="${lineClass}">${displayLine}</div>`;
                }
                
                if (html === '') {
                    logDiv.innerHTML = '<div class="log-line">暂无日志内容</div>';
                } else {
                    logDiv.innerHTML = html;
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
            } catch(e) {
                console.error('刷新日志失败:', e);
                const logDiv = document.getElementById('logContent');
                if (logDiv) logDiv.innerHTML = '加载日志失败: ' + e.message;
            }
        }
        
        async function installLlama() {
            if (confirm('开始完整安装 llama.cpp？\\n这可能需要 10-30 分钟。')) {
                const btn = document.getElementById('installBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 安装中...';
                const result = await fetchAPI('/api/install', 'POST');
                alert(result.message);
                startMonitoring();
                btn.disabled = false;
                btn.innerHTML = '🚀 完整安装 llama.cpp';
            }
        }
        
        async function updateLlama() {
            if (confirm('更新 llama.cpp 到最新稳定版本？\\n这将切换代码到最新版本，然后需要重新编译。')) {
                const btn = document.getElementById('updateBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 更新中...';
                const result = await fetchAPI('/api/update', 'POST');
                alert(result.message);
                refreshStatus();
                btn.disabled = false;
                btn.innerHTML = '🔄 更新llama.cpp';
            }
        }
        
        async function rebuildLlama() {
            if (confirm('重新编译 llama.cpp？')) {
                const btn = document.getElementById('rebuildBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 编译中...';
                const result = await fetchAPI('/api/rebuild', 'POST');
                alert(result.message);
                refreshStatus();
                btn.disabled = false;
                btn.innerHTML = '🔨 重新编译';
            }
        }
        
        async function cleanBuild() {
            if (confirm('清理所有编译产物？')) {
                const result = await fetchAPI('/api/clean', 'POST');
                alert(result.message);
                refreshStatus();
            }
        }
        
        async function deleteAll() {
            if (confirm('⚠️ 警告：这将删除整个 llama.cpp 目录及其所有文件！\\n删除后需要重新点击「完整安装」。\\n确定要继续吗？')) {
                const btn = document.getElementById('deleteBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 删除中...';
                const result = await fetchAPI('/api/delete_all', 'POST');
                alert(result.message);
                refreshStatus();
                refreshLog();
                btn.disabled = false;
                btn.innerHTML = '🗑️ 删除所有';
            }
        }
        
        // ==================== LlamaPanel 更新相关（模态框版） ====================
        let updatePollInterval = null;
        let updateLogRefreshInterval = null;
        let updateStartTime = null;
        
        async function updateLlamaPanel() {
            if (confirm('🔄 更新 LlamaPanel 面板？\\n\\n将从 GitHub 拉取最新代码并更新依赖。\\n如果系统配置了 NOPASSWD sudo，服务将自动重启。\\n继续吗？')) {
                const btn = document.getElementById('updatePanelBtn');
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 更新中...';
                
                // 打开模态框
                openUpdateModal();
                
                try {
                    const result = await fetchAPI('/api/update_panel', 'POST');
                    if (result.success) {
                        // 开始轮询更新日志和状态
                        startUpdateLogPolling();
                        startUpdateStatusPolling();
                    } else {
                        updateModalSetStatus('fail', '启动失败');
                        updateModalSetFooter('❌ ' + result.message, true);
                        enableModalCloseAfterDelay(3000);
                        btn.disabled = false;
                        btn.innerHTML = '🔄 更新 LlamaPanel';
                    }
                } catch(e) {
                    updateModalSetStatus('fail', '请求失败');
                    updateModalSetFooter('❌ 请求失败: ' + e.message, true);
                    enableModalCloseAfterDelay(3000);
                    btn.disabled = false;
                    btn.innerHTML = '🔄 更新 LlamaPanel';
                }
            }
        }
        
        // ---- 模态框控制 ----
        function openUpdateModal() {
            const modal = document.getElementById('updateModal');
            const body = document.getElementById('updateModalBody');
            const closeBtn = document.getElementById('updateModalCloseBtn');
            if (modal) modal.classList.add('active');
            if (body) body.innerHTML = '<div class="log-line">正在启动更新任务...</div>';
            if (closeBtn) closeBtn.disabled = true;
            updateModalSetStatus('running', '更新中...');
            updateModalSetFooter('<span class="spinner"></span> 更新执行中，请勿关闭此窗口...', false);
            updateStartTime = Date.now();
            updateModalUpdateTime();
        }
        
        function closeUpdateModal() {
            const modal = document.getElementById('updateModal');
            if (modal) modal.classList.remove('active');
            // 停止所有轮询
            stopUpdatePolling();
            // 恢复按钮
            const btn = document.getElementById('updatePanelBtn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🔄 更新 LlamaPanel';
            }
        }
        
        function updateModalSetStatus(type, text) {
            const badge = document.getElementById('updateModalStatus');
            if (!badge) return;
            badge.className = 'modal-status';
            if (type === 'running') badge.classList.add('modal-status-running');
            else if (type === 'success') badge.classList.add('modal-status-success');
            else if (type === 'fail') badge.classList.add('modal-status-fail');
            badge.textContent = text;
        }
        
        function updateModalSetFooter(html, isFinal) {
            const footer = document.getElementById('updateModalFooter');
            if (!footer) return;
            footer.innerHTML = html;
            if (isFinal) {
                // 不再显示 spinner
            }
        }
        
        function updateModalUpdateTime() {
            const el = document.getElementById('updateModalTime');
            if (!el || !updateStartTime) return;
            const elapsed = Math.floor((Date.now() - updateStartTime) / 1000);
            const m = Math.floor(elapsed / 60);
            const s = elapsed % 60;
            el.textContent = `⏱ ${m}:${s.toString().padStart(2, '0')}`;
        }
        
        function enableModalCloseAfterDelay(delayMs) {
            setTimeout(() => {
                const closeBtn = document.getElementById('updateModalCloseBtn');
                if (closeBtn) closeBtn.disabled = false;
            }, delayMs);
        }
        
        // ---- 更新日志轮询 ----
        async function refreshUpdateLog() {
            try {
                const response = await fetch('/api/update_panel_log');
                const data = await response.json();
                const logDiv = document.getElementById('updateModalBody');
                if (!logDiv) return;
                
                if (!data.success || !data.log || data.log.trim() === '') {
                    // 保留现有内容，不覆盖
                    return;
                }
                
                let text = data.log;
                text = text.replace(/\\\\n/g, '\\n');
                text = text.replace(/\\\\r\\\\n/g, '\\n');
                const lines = text.split('\\n');
                
                let html = '';
                for (let i = 0; i < lines.length; i++) {
                    let line = lines[i];
                    if (line.trim() === '') continue;
                    
                    let lineClass = 'log-line';
                    let displayLine = escapeHtml(line);
                    
                    if (line.includes('[ERR]') || line.includes('error') || line.includes('Error') || line.includes('失败') || line.includes('❌')) {
                        lineClass += ' log-error';
                    } else if (line.includes('✅')) {
                        lineClass += ' log-success';
                    } else if (line.includes('⚠️')) {
                        lineClass += ' log-warning';
                        displayLine = '⚠️ ' + displayLine;
                    } else if (line.includes('执行:')) {
                        lineClass += ' log-command';
                        displayLine = '🔧 ' + displayLine;
                    } else if (line.includes('==========')) {
                        lineClass += ' log-separator';
                    } else if (line.includes('完成') || line.includes('成功')) {
                        lineClass += ' log-success';
                    }
                    
                    html += `<div class="${lineClass}">${displayLine}</div>`;
                }
                
                if (html) {
                    logDiv.innerHTML = html;
                    logDiv.scrollTop = logDiv.scrollHeight;
                }
                
                // 更新时间显示
                updateModalUpdateTime();
            } catch(e) {
                console.error('刷新更新日志失败:', e);
            }
        }
        
        // ---- 更新状态轮询 ----
        async function refreshUpdateStatus() {
            try {
                const status = await fetchAPI('/api/update_panel_status');
                const btn = document.getElementById('updatePanelBtn');
                
                if (!status.running) {
                    // 更新已完成，停止日志轮询（但保留状态轮询用于最终状态更新）
                    if (updateLogRefreshInterval) {
                        clearInterval(updateLogRefreshInterval);
                        updateLogRefreshInterval = null;
                    }
                    
                    // 最后再刷新一次日志确保看到完整内容
                    await refreshUpdateLog();
                    
                    if (status.success === true) {
                        const msg = status.message || '更新完成';
                        if (msg.includes('最新版本')) {
                            // 已是最新
                            updateModalSetStatus('success', '已是最新版本 ✅');
                            updateModalSetFooter('✅ 已经是最新版本，无需更新', true);
                            enableModalCloseAfterDelay(2000);
                            if (btn) {
                                btn.disabled = false;
                                btn.innerHTML = '🔄 更新 LlamaPanel';
                            }
                            // 停止状态轮询
                            stopUpdateStatusPolling();
                        } else {
                            // 更新成功
                            updateModalSetStatus('success', '更新完成 ✅');
                            updateModalSetFooter('✅ 更新成功！点击确定重新加载页面以应用更新。', false);
                            // 启用关闭按钮
                            const closeBtn = document.getElementById('updateModalCloseBtn');
                            if (closeBtn) closeBtn.disabled = false;
                            setTimeout(() => {
                                if (confirm('✅ LlamaPanel 更新完成！\\n\\n系统需要重新加载页面以应用更新。\\n点击"确定"立即刷新。')) {
                                    location.reload();
                                } else {
                                    updateModalSetFooter('⏸ 已暂停，您可以稍后手动刷新页面', true);
                                    if (btn) {
                                        btn.disabled = false;
                                        btn.innerHTML = '🔄 更新 LlamaPanel';
                                    }
                                    stopUpdateStatusPolling();
                                }
                            }, 1500);
                        }
                    } else if (status.success === false) {
                        // 更新失败
                        updateModalSetStatus('fail', '更新失败 ❌');
                        updateModalSetFooter('❌ ' + (status.message || '更新失败，请检查日志'), true);
                        enableModalCloseAfterDelay(5000);
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '🔄 更新 LlamaPanel';
                        }
                        // 5秒后自动关闭模态框
                        setTimeout(() => {
                            closeUpdateModal();
                        }, 8000);
                        stopUpdateStatusPolling();
                    }
                }
            } catch(e) {
                console.error('刷新更新状态失败:', e);
            }
        }
        
        function startUpdateLogPolling() {
            if (updateLogRefreshInterval) clearInterval(updateLogRefreshInterval);
            refreshUpdateLog();
            updateLogRefreshInterval = setInterval(refreshUpdateLog, 2000);
        }
        
        function startUpdateStatusPolling() {
            if (updatePollInterval) clearInterval(updatePollInterval);
            updatePollInterval = setInterval(refreshUpdateStatus, 3000);
        }
        
        function stopUpdateStatusPolling() {
            if (updatePollInterval) {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
            }
        }
        
        function stopUpdatePolling() {
            if (updateLogRefreshInterval) {
                clearInterval(updateLogRefreshInterval);
                updateLogRefreshInterval = null;
            }
            if (updatePollInterval) {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
            }
            const btn = document.getElementById('updatePanelBtn');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '🔄 更新 LlamaPanel';
            }
        }
        
        function startMonitoring() {
            // 安装/编译开始后，立即刷新一次状态
            refreshStatus();
        }
        
        // 初始化
        refreshStatus();
        refreshLog();
        startAutoRefresh();
        bindAutoRefreshCheckbox();
        // 统一使用5秒间隔刷新状态（避免多个定时器冲突）
        setInterval(refreshStatus, 5000);
    </script>
</body>
</html>
'''

@app.get("/")
async def root():
    return HTMLResponse(content=HTML_PAGE)

@app.get("/api/status")
async def get_status():
    return installer.get_status()

@app.get("/api/log")
async def get_log():
    log_file = installer.log_file
    if not log_file.exists():
        return "暂无日志"
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if not content or content.strip() == '':
        return "暂无日志"
    
    content = content.replace('\\n', '\n')
    content = content.replace('\\r\\n', '\n')
    
    return content

@app.post("/api/install")
async def install_llama(background_tasks: BackgroundTasks):
    if installer._install_running:
        return {"success": False, "message": "安装已在运行中"}
    def run_install():
        installer._install_running = True
        try:
            installer.full_install()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_install)
    return {"success": True, "message": "安装任务已启动，请查看日志面板"}

@app.post("/api/update")
async def update_llama(background_tasks: BackgroundTasks):
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_update():
        installer._install_running = True
        try:
            installer.update_llama_cpp()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_update)
    return {"success": True, "message": "更新任务已启动，请查看日志面板"}

@app.post("/api/rebuild")
async def rebuild_llama(background_tasks: BackgroundTasks):
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_rebuild():
        installer._install_running = True
        try:
            installer.rebuild()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_rebuild)
    return {"success": True, "message": "重新编译任务已启动，请查看日志面板"}

@app.post("/api/clean")
async def clean_build(background_tasks: BackgroundTasks):
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_clean():
        installer._install_running = True
        try:
            installer.clean_build()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_clean)
    return {"success": True, "message": "清理任务已启动，请查看日志面板"}

@app.post("/api/delete_all")
async def delete_all(background_tasks: BackgroundTasks):
    if installer._install_running:
        return {"success": False, "message": "已有任务正在运行中"}
    def run_delete():
        installer._install_running = True
        try:
            installer.delete_all()
        finally:
            installer._install_running = False
    background_tasks.add_task(run_delete)
    return {"success": True, "message": "删除任务已启动，请查看日志面板"}

@app.post("/api/update_panel")
async def update_panel(background_tasks: BackgroundTasks):
    """更新 LlamaPanel 自身"""
    if not hasattr(update_panel, '_lock'):
        update_panel._lock = threading.Lock()
        update_panel._running = False
    
    # 加锁检查并设置运行标志，防止竞态条件
    with update_panel._lock:
        if update_panel._running:
            return {"success": False, "message": "更新任务已在运行中"}
        update_panel._running = True
    
    def run_update():
        try:
            update_llamapanel()
        except Exception as e:
            print(f"更新异常: {e}")
        finally:
            with update_panel._lock:
                update_panel._running = False
    
    background_tasks.add_task(run_update)
    return {"success": True, "message": "LlamaPanel 更新任务已启动，请查看更新日志"}

@app.get("/api/update_panel_log")
async def get_update_panel_log():
    """读取 LlamaPanel 更新日志"""
    log_file = LOGS_DIR / "update.log"
    if not log_file.exists():
        return {"success": True, "log": "", "message": "暂无更新日志"}
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.read()
        if not content.strip():
            return {"success": True, "log": "", "message": "暂无更新日志"}
        return {"success": True, "log": content}
    except Exception as e:
        return {"success": False, "log": "", "message": f"读取日志失败: {e}"}

@app.get("/api/update_panel_status")
async def get_update_panel_status():
    """查询 LlamaPanel 更新状态（前端轮询用）"""
    with _update_panel_lock:
        status = dict(_update_panel_status)
    # 如果更新日志有内容，获取最后几行作为摘要
    summary = ""
    log_file = LOGS_DIR / "update.log"
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if lines:
                # 取最后5行非空行
                recent = [l.strip() for l in lines if l.strip()][-5:]
                summary = "\n".join(recent)
        except:
            pass
    status["summary"] = summary
    return status

if __name__ == "__main__":
    import uvicorn
    print("🦙 LlamaPanel 启动中...")
    print("访问地址: http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
