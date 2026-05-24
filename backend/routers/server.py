#!/usr/bin/env python3
"""
llama.cpp Server 参数配置与管理路由
提供完整的 llama-server 命令行参数配置、保存、启动、停止功能
"""
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/api/server", tags=["server"])

# ==================== 全局服务器进程状态 ====================
_server_process = None
_server_running = False
_server_start_time = None
_server_pid = None
_server_lock = threading.Lock()

# ==================== 配置存储路径（惰性初始化，避免导入时因权限崩溃） ====================
_CONFIG_DIR = None
_CONFIG_FILE = None
_SERVER_LOG_FILE = None


def _ensure_config_dir():
    """确保配置目录存在（惰性初始化，含错误包容）"""
    global _CONFIG_DIR, _CONFIG_FILE, _SERVER_LOG_FILE
    if _CONFIG_DIR is not None:
        return
    try:
        from config import DATA_DIR
        _CONFIG_DIR = DATA_DIR / "server_configs"
    except Exception:
        _CONFIG_DIR = Path("/data/llamapanel/server_configs")
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[server] ⚠️ 创建配置目录失败: {e}，将使用临时目录")
        import tempfile
        _CONFIG_DIR = Path(tempfile.gettempdir()) / "llamapanel_server_config"
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE = _CONFIG_DIR / "llama_server_config.json"
    _SERVER_LOG_FILE = _CONFIG_DIR / "server_process.log"
    print(f"[server] 配置目录: {_CONFIG_DIR}")


def get_config_dir() -> Path:
    _ensure_config_dir()
    return _CONFIG_DIR


def get_config_file() -> Path:
    _ensure_config_dir()
    return _CONFIG_FILE


def get_server_log_file() -> Path:
    _ensure_config_dir()
    return _SERVER_LOG_FILE


# ==================== 读取 HTML 模板（含错误包容） ====================
SERVER_HTML = "<h1>页面加载失败</h1>"
try:
    html_path = Path(__file__).parent.parent / "templates" / "server.html"
    if html_path.exists():
        with open(html_path, 'r', encoding='utf-8') as f:
            SERVER_HTML = f.read()
except Exception as e:
    print(f"[server] ⚠️ 读取模板失败: {e}")
    SERVER_HTML = "<h1>页面模板加载失败，请检查模板文件</h1>"

# ==================== llama-server 所有可用参数定义 ====================
# 这些参数用于前端表单的自动生成和验证
SERVER_PARAMS_META = {
    # ===== 模型与路径 =====
    "model": {
        "section": "模型与路径",
        "flag": "-m",
        "type": "file_picker",
        "label": "模型文件路径 (GGUF)",
        "description": "要加载的 GGUF 模型文件路径。可使用软链接目录中的文件。",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/模型名称.gguf",
        "required": True,
    },
    "mmproj": {
        "section": "模型与路径",
        "flag": "--mmproj",
        "type": "text",
        "label": "多模态投影文件 (mmproj)",
        "description": "多模态模型的投影器文件路径（如 LLaVA 等视觉模型）",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/模型文件夹/mmproj-file.gguf",
    },
    "lora": {
        "section": "模型与路径",
        "flag": "--lora",
        "type": "text",
        "label": "LoRA 适配器",
        "description": "LoRA 适配器文件路径（可多次指定，用逗号分隔）",
        "default": "",
        "placeholder": "/path/to/lora-adapter.gguf",
    },
    "lora_base": {
        "section": "模型与路径",
        "flag": "--lora-base",
        "type": "text",
        "label": "LoRA 基座模型",
        "description": "用于 LoRA 的可选基座模型路径",
        "default": "",
        "placeholder": "/path/to/base-model.gguf",
    },

    # ===== GPU 与加速 =====
    "n_gpu_layers": {
        "section": "GPU 与加速",
        "flag": "-ngl",
        "type": "number",
        "label": "GPU 层数 (-ngl)",
        "description": "卸载到 GPU 的层数。设为 -1 表示全部层都使用 GPU。设为 0 表示纯 CPU。",
        "default": "0",
        "placeholder": "0",
        "min": -1,
        "max": 999,
    },
    "no_kv_offload": {
        "section": "GPU 与加速",
        "flag": "--no-kv-offload",
        "type": "checkbox",
        "label": "禁用 KV Cache GPU 卸载",
        "description": "禁用 KV 缓存到 GPU 的卸载（实验性功能）",
        "default": False,
    },
    "cache_type_k": {
        "section": "GPU 与加速",
        "flag": "--cache-type-k",
        "type": "select",
        "label": "K Cache 量化类型",
        "description": "Key 缓存的数据类型。q4_0/q8_0/f16 等，量化可节省显存但略微降低精度。",
        "default": "f16",
        "options": [
            {"value": "f16", "label": "f16 (半精度)"},
            {"value": "q4_0", "label": "q4_0 (4-bit 量化)"},
            {"value": "q8_0", "label": "q8_0 (8-bit 量化)"},
            {"value": "q4_1", "label": "q4_1 (4-bit 量化+v)"},
        ],
    },
    "cache_type_v": {
        "section": "GPU 与加速",
        "flag": "--cache-type-v",
        "type": "select",
        "label": "V Cache 量化类型",
        "description": "Value 缓存的数据类型。q4_0 可大幅节省显存。",
        "default": "f16",
        "options": [
            {"value": "f16", "label": "f16 (半精度)"},
            {"value": "q4_0", "label": "q4_0 (4-bit 量化)"},
            {"value": "q8_0", "label": "q8_0 (8-bit 量化)"},
            {"value": "q4_1", "label": "q4_1 (4-bit 量化+v)"},
        ],
    },
    "no_unload": {
        "section": "GPU 与加速",
        "flag": "--no-unload",
        "type": "checkbox",
        "label": "模型常驻 GPU (no-unload)",
        "description": "模型推理后不卸载出 GPU 显存，下次推理更快。开启后模型常驻 VRAM。",
        "default": False,
    },
    "tensor_split": {
        "section": "GPU 与加速",
        "flag": "-ts",
        "type": "text",
        "label": "张量拆分比例",
        "description": "多 GPU 时张量拆分比例，用逗号分隔（如: 2,1 表示 GPU0:GPU1=2:1）",
        "default": "",
        "placeholder": "2,1",
    },
    "mlock": {
        "section": "GPU 与加速",
        "flag": "--mlock",
        "type": "checkbox",
        "label": "锁定模型到内存 (mlock)",
        "description": "将模型锁定在物理内存中，防止被交换到磁盘。可提高性能但占用更多内存。",
        "default": False,
    },
    "no_mmap": {
        "section": "GPU 与加速",
        "flag": "--no-mmap",
        "type": "checkbox",
        "label": "禁用内存映射 (no-mmap)",
        "description": "禁用 mmap() 加载模型。对于某些网络文件系统或特殊需求时使用。",
        "default": False,
    },

    # ===== 上下文与内存 =====
    "ctx_size": {
        "section": "上下文与内存",
        "flag": "-c",
        "type": "number",
        "label": "上下文大小 (ctx-size)",
        "description": "Token 上下文窗口大小。越大可记住更多对话内容，但消耗更多显存/内存。",
        "default": "4096",
        "placeholder": "4096",
        "min": 128,
        "max": 999999,
        "step": 128,
    },
    "rope_freq_base": {
        "section": "上下文与内存",
        "flag": "--rope-freq-base",
        "type": "number",
        "label": "RoPE 频率基数",
        "description": "RoPE 频率基数，用于扩展上下文窗口（如 800000.0 可将 4K 模型扩展到 32K）",
        "default": "",
        "placeholder": "如: 800000.0",
        "step": 0.1,
    },
    "rope_freq_scale": {
        "section": "上下文与内存",
        "flag": "--rope-freq-scale",
        "type": "number",
        "label": "RoPE 频率缩放",
        "description": "RoPE 频率缩放因子。设为 0.25 可将 4K 模型扩展到 16K 上下文。",
        "default": "",
        "placeholder": "如: 0.25",
        "step": 0.01,
    },
    "rope_scaling": {
        "section": "上下文与内存",
        "flag": "--rope-scaling",
        "type": "select",
        "label": "RoPE 缩放类型",
        "description": "上下文扩展时使用的 RoPE 缩放类型",
        "default": "yarn",
        "options": [
            {"value": "linear", "label": "linear (线性)"},
            {"value": "yarn", "label": "yarn (YaRN)"},
        ],
    },
    "rope_scale": {
        "section": "上下文与内存",
        "flag": "--rope-scale",
        "type": "number",
        "label": "RoPE 上下文缩放",
        "description": "RoPE 上下文扩展的缩放因子。配合 rope-scaling=yarn 使用时设为 2.0。",
        "default": "2.0",
        "placeholder": "2.0",
        "min": 0.0,
        "step": 0.5,
    },
    "yarn_orig_ctx": {
        "section": "上下文与内存",
        "flag": "--yarn-orig-ctx",
        "type": "number",
        "label": "YaRN 原始上下文大小",
        "description": "YaRN 缩放时模型的原始上下文大小。如 32768 表示模型原生支持 32K 上下文。",
        "default": "32768",
        "placeholder": "32768",
        "min": 128,
        "step": 128,
    },

    # ===== 采样参数 =====
    "temp": {
        "section": "采样参数",
        "flag": "--temp",
        "type": "number",
        "label": "温度 (Temperature)",
        "description": "生成温度。越高越随机（创新），越低越确定（保守）。范围 0.0 ~ 2.0",
        "default": "0.8",
        "placeholder": "0.8",
        "min": 0.0,
        "max": 2.0,
        "step": 0.01,
    },
    "top_k": {
        "section": "采样参数",
        "flag": "--top-k",
        "type": "number",
        "label": "Top-K",
        "description": "只从前 K 个最可能的 token 中采样。0=禁用。",
        "default": "40",
        "placeholder": "40",
        "min": 0,
        "max": 200,
    },
    "top_p": {
        "section": "采样参数",
        "flag": "--top-p",
        "type": "number",
        "label": "Top-P (核采样)",
        "description": "累积概率阈值采样。0.0=禁用。",
        "default": "0.95",
        "placeholder": "0.95",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    "min_p": {
        "section": "采样参数",
        "flag": "--min-p",
        "type": "number",
        "label": "Min-P",
        "description": "最小概率阈值。token 概率低于最可能 token 概率 × min-p 的将被过滤。",
        "default": "0.05",
        "placeholder": "0.05",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    "repeat_penalty": {
        "section": "采样参数",
        "flag": "--repeat-penalty",
        "type": "number",
        "label": "重复惩罚",
        "description": "重复惩罚系数。1.0=无惩罚，1.1=中等惩罚，1.2=强惩罚。",
        "default": "1.1",
        "placeholder": "1.1",
        "min": 1.0,
        "max": 2.0,
        "step": 0.01,
    },
    "repeat_last_n": {
        "section": "采样参数",
        "flag": "--repeat-last-n",
        "type": "number",
        "label": "重复惩罚窗口",
        "description": "最后 N 个 token 内应用重复惩罚。0=禁用，-1=ctx_size。",
        "default": "64",
        "placeholder": "64",
        "min": -1,
        "max": 99999,
    },
    "presence_penalty": {
        "section": "采样参数",
        "flag": "--presence-penalty",
        "type": "number",
        "label": "存在惩罚 (presence-penalty)",
        "description": "对已出现的 token 施加惩罚，鼓励生成新主题。0.0=禁用，正值=惩罚已出现 token。",
        "default": "0.0",
        "placeholder": "0.0",
        "min": -2.0,
        "max": 2.0,
        "step": 0.01,
    },

    # ===== 服务器设置 =====
    "host": {
        "section": "服务器设置",
        "flag": "--host",
        "type": "text",
        "label": "监听地址 (Host)",
        "description": "服务器监听地址。0.0.0.0=所有网卡，127.0.0.1=仅本机。",
        "default": "127.0.0.1",
        "placeholder": "127.0.0.1",
    },
    "port": {
        "section": "服务器设置",
        "flag": "--port",
        "type": "number",
        "label": "监听端口 (Port)",
        "description": "服务器 HTTP 监听端口。",
        "default": "8080",
        "placeholder": "8080",
        "min": 1,
        "max": 65535,
    },
    "timeout": {
        "section": "服务器设置",
        "flag": "--timeout",
        "type": "number",
        "label": "读写超时 (秒)",
        "description": "服务器读取和写入操作的超时时间（秒）。",
        "default": "600",
        "placeholder": "600",
        "min": 10,
        "max": 86400,
    },
    "parallel": {
        "section": "服务器设置",
        "flag": "-np",
        "type": "number",
        "label": "并行序列数",
        "description": "同时处理的序列数（并发请求数）。",
        "default": "1",
        "placeholder": "1",
        "min": 1,
        "max": 999,
    },
    "cont_batching": {
        "section": "服务器设置",
        "flag": "-cb",
        "type": "checkbox",
        "label": "启用持续批处理",
        "description": "启用持续批处理，同一批中动态添加/移除序列，提升吞吐量。",
        "default": True,
    },
    "slots": {
        "section": "服务器设置",
        "flag": "--slots",
        "type": "number",
        "label": "最大 slots 数",
        "description": "在持续批处理模式下，最大 slot 数量（每个 slot 处理一个请求）。",
        "default": "",
        "placeholder": "留空则等于 parallel",
        "min": 1,
        "max": 999,
    },
    "slot_save_path": {
        "section": "服务器设置",
        "flag": "--slot-save-path",
        "type": "text",
        "label": "Slot KV 缓存保存路径",
        "description": "保存 slot KV 缓存的路径（用于持久化对话状态）",
        "default": "",
        "placeholder": "/data/llamapanel/slot_cache",
    },
    "embeddings": {
        "section": "服务器设置",
        "flag": "--embeddings",
        "type": "checkbox",
        "label": "启用嵌入模式",
        "description": "启用嵌入向量提取模式（兼容 OpenAI embeddings API）。",
        "default": False,
    },
    "no_webui": {
        "section": "服务器设置",
        "flag": "--no-webui",
        "type": "checkbox",
        "label": "禁用 WebUI",
        "description": "不启动内置的 Web 聊天界面。",
        "default": False,
    },
    "jinja": {
        "section": "服务器设置",
        "flag": "--jinja",
        "type": "checkbox",
        "label": "启用 Jinja2 模板",
        "description": "使用模型的 Jinja2 聊天模板来处理对话格式（需模型支持）。",
        "default": True,
    },
    "mcp": {
        "section": "服务器设置",
        "flag": "--mcp",
        "type": "checkbox",
        "label": "启用 MCP Server",
        "description": "启用 Model Context Protocol (MCP) 服务器功能，允许外部工具与模型交互。",
        "default": False,
    },

    # ===== 线程与性能 =====
    "threads": {
        "section": "线程与性能",
        "flag": "-t",
        "type": "number",
        "label": "生成线程数",
        "description": "Token 生成阶段使用的线程数。一般设为 CPU 物理核心数。",
        "default": "8",
        "placeholder": "8",
        "min": 1,
        "max": 256,
    },
    "threads_batch": {
        "section": "线程与性能",
        "flag": "--threads-batch",
        "type": "number",
        "label": "批处理线程数",
        "description": "Prompt 批处理阶段使用的线程数。留空则与生成线程数相同。",
        "default": "",
        "placeholder": "留空则等于生成线程数",
        "min": 1,
        "max": 256,
    },
    "batch_size": {
        "section": "线程与性能",
        "flag": "-b",
        "type": "number",
        "label": "批处理大小 (batch-size)",
        "description": "Prompt 处理的批处理 token 数。越大越快但消耗更多内存。",
        "default": "2048",
        "placeholder": "2048",
        "min": 32,
        "max": 999999,
    },
    "ubatch_size": {
        "section": "线程与性能",
        "flag": "-ub",
        "type": "number",
        "label": "物理批处理大小 (ubatch-size)",
        "description": "物理批处理大小。影响计算效率。一般 ≤ batch-size。",
        "default": "512",
        "placeholder": "512",
        "min": 32,
        "max": 999999,
    },
    "flash_attn": {
        "section": "线程与性能",
        "flag": "--flash-attn",
        "type": "select",
        "label": "Flash Attention",
        "description": "使用 Flash Attention 加速计算，减少显存占用。需要模型支持。",
        "default": "on",
        "options": [
            {"value": "on", "label": "启用 (on)"},
            {"value": "off", "label": "禁用 (off)"},
            {"value": "auto", "label": "自动 (auto)"},
        ],
    },
    "n_cpu_moe": {
        "section": "线程与性能",
        "flag": "--n-cpu-moe",
        "type": "number",
        "label": "MoE CPU 核心数",
        "description": "混合专家模型 (MoE) 中，使用 CPU 处理 expert 的线程数。设为 0=禁用，建议 32 或根据 CPU 核心数设置。",
        "default": "0",
        "placeholder": "32",
        "min": 0,
        "max": 256,
    },
}

# 按分区排序的参数列表
SERVER_PARAMS_SECTIONS = [
    "模型与路径",
    "GPU 与加速",
    "上下文与内存",
    "采样参数",
    "服务器设置",
    "线程与性能",
]

# ==================== 辅助函数 ====================


def find_llama_server() -> Optional[str]:
    """查找 llama-server 可执行文件路径"""
    from config import BUILD_DIR, LLAMA_DIR
    
    candidates = [
        BUILD_DIR / "bin" / "llama-server",
        BUILD_DIR / "llama-server",
        LLAMA_DIR / "llama-server",
    ]
    # 也尝试在 PATH 中查找
    try:
        which_result = subprocess.run(
            ["which", "llama-server"], capture_output=True, text=True, timeout=5
        )
        if which_result.returncode == 0 and which_result.stdout.strip():
            candidates.insert(0, Path(which_result.stdout.strip()))
    except:
        pass
    
    for p in candidates:
        if p.exists() and os.access(str(p), os.X_OK):
            return str(p)
    return None


def get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    config = {}
    for key, meta in SERVER_PARAMS_META.items():
        config[key] = meta["default"]
    return config


def load_config() -> Dict[str, Any]:
    """从文件加载已保存的配置"""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并默认值，确保新增参数也有值
            defaults = get_default_config()
            defaults.update(saved)
            return defaults
        except Exception as e:
            print(f"[server] 加载配置失败: {e}")
    return get_default_config()


def save_config(config: Dict[str, Any]) -> bool:
    """保存配置到文件"""
    try:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(get_config_file(), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[server] 保存配置失败: {e}")
        return False


def build_command(config: Dict[str, Any]) -> list:
    """根据配置构建 llama-server 命令行参数"""
    server_path = find_llama_server()
    if not server_path:
        raise FileNotFoundError("未找到 llama-server 可执行文件，请先编译 llama.cpp")
    
    cmd = [server_path]
    
    for key, meta in SERVER_PARAMS_META.items():
        value = config.get(key, meta["default"])
        
        # 跳过空值（非必填的文本字段）
        if value is None or value == "":
            continue
        
        # 跳过假值（checkbox 未选中）
        if meta["type"] == "checkbox":
            if value is True or value == "true":
                cmd.append(meta["flag"])
            continue
        
        # select / 数字 / 文本值：添加参数名和值
        cmd.append(meta["flag"])
        cmd.append(str(value))
    
    return cmd


def write_server_log(message: str):
    """写入服务器进程日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(f"[server] {log_msg}")
    try:
        log_file = get_server_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"[server] 写入日志失败: {e}")


def server_process_runner(cmd: list):
    """在后台线程中运行 llama-server 进程"""
    global _server_process, _server_running, _server_start_time, _server_pid
    
    write_server_log(f"🚀 启动命令: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        
        with _server_lock:
            _server_process = process
            _server_pid = process.pid
            _server_running = True
            _server_start_time = time.time()
        
        write_server_log(f"✅ 服务器已启动，PID: {process.pid}")
        
        # 实时读取输出
        for line in process.stdout:
            line = line.rstrip()
            if line:
                write_server_log(line)
        
        returncode = process.wait()
        
        with _server_lock:
            _server_running = False
            _server_process = None
            _server_pid = None
        
        if returncode == 0:
            write_server_log(f"✅ 服务器正常退出")
        else:
            write_server_log(f"⚠️ 服务器异常退出，返回码: {returncode}")
    
    except Exception as e:
        write_server_log(f"❌ 服务器运行异常: {e}")
        with _server_lock:
            _server_running = False
            _server_process = None
            _server_pid = None


# ==================== API 端点 ====================


@router.get("/page", response_class=HTMLResponse)
async def server_page():
    """服务器参数配置页面"""
    return HTMLResponse(content=SERVER_HTML)


@router.get("/params-meta")
async def get_params_meta():
    """获取所有参数元数据（前端用于动态渲染表单）"""
    return {
        "success": True,
        "params": SERVER_PARAMS_META,
        "sections": SERVER_PARAMS_SECTIONS,
    }


@router.get("/config")
async def get_config():
    """获取已保存的服务器配置"""
    config = load_config()
    return {"success": True, "config": config}


@router.post("/config")
async def set_config(payload: dict = Body(...)):
    """保存服务器配置"""
    config = payload.get("config", {})
    if not config:
        return {"success": False, "message": "配置数据为空"}
    
    if save_config(config):
        return {"success": True, "message": "配置已保存"}
    else:
        return {"success": False, "message": "配置保存失败"}


@router.post("/start")
async def start_server():
    """启动 llama-server"""
    global _server_running
    
    # 检查是否已在运行
    with _server_lock:
        if _server_running:
            return {"success": False, "message": "服务器已在运行中"}
    
    # 查找 llama-server
    server_path = find_llama_server()
    if not server_path:
        return {"success": False, "message": "未找到 llama-server 可执行文件。请先在主页中编译 llama.cpp。"}
    
    # 加载配置并构建命令
    config = load_config()
    
    # 检查模型文件
    model_path = config.get("model", "")
    if not model_path:
        return {"success": False, "message": "请先配置模型文件路径 (-m)"}
    
    if not os.path.exists(model_path):
        return {"success": False, "message": f"模型文件不存在: {model_path}"}
    
    try:
        cmd = build_command(config)
    except FileNotFoundError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"构建命令失败: {e}"}
    
    # 清空旧日志
    try:
        if get_server_log_file().exists():
            get_server_log_file().unlink()
    except:
        pass
    
    write_server_log("=" * 60)
    write_server_log("配置参数:")
    for key, meta in SERVER_PARAMS_META.items():
        val = config.get(key, "")
        if val is not None and str(val).strip():
            write_server_log(f"  {meta['flag']} {meta['label']}: {val}")
    write_server_log("=" * 60)
    
    # 在后台线程启动服务器
    thread = threading.Thread(target=server_process_runner, args=(cmd,), daemon=True)
    thread.start()
    
    # 等待一小段时间检查是否启动成功
    time.sleep(1)
    
    with _server_lock:
        if _server_running:
            return {
                "success": True,
                "message": f"服务器已启动 (PID: {_server_pid})",
                "pid": _server_pid,
            }
        else:
            # 可能启动失败，读取日志
            log_content = ""
            try:
                if get_server_log_file().exists():
                    with open(get_server_log_file(), "r", encoding="utf-8") as f:
                        log_content = f.read()
            except:
                pass
            return {
                "success": False,
                "message": "服务器启动失败，请查看日志了解详情",
                "log": log_content[-1000:] if log_content else "",
            }


@router.post("/stop")
async def stop_server():
    """停止 llama-server 进程"""
    global _server_process, _server_running, _server_pid
    
    with _server_lock:
        if not _server_running or _server_process is None:
            return {"success": False, "message": "服务器未在运行"}
        
        pid = _server_pid
        process = _server_process
    
    write_server_log(f"🛑 正在停止服务器 (PID: {pid})...")
    
    try:
        # 先发 SIGTERM 信号优雅退出
        os.kill(pid, signal.SIGTERM)
        
        # 等待最多 10 秒
        for _ in range(20):
            time.sleep(0.5)
            if not _server_running:
                break
            # 检查进程是否还活着
            try:
                os.kill(pid, 0)  # 信号 0 仅检查进程是否存在
            except OSError:
                with _server_lock:
                    _server_running = False
                    _server_process = None
                    _server_pid = None
                break
        else:
            # 如果 10 秒后还没结束，强行杀死
            write_server_log("⚠️ 进程未响应 SIGTERM，发送 SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
    except ProcessLookupError:
        pass
    except Exception as e:
        write_server_log(f"❌ 停止服务器失败: {e}")
        return {"success": False, "message": f"停止失败: {e}"}
    
    with _server_lock:
        _server_running = False
        _server_process = None
        _server_pid = None
    
    write_server_log("✅ 服务器已停止")
    return {"success": True, "message": "服务器已停止"}


@router.get("/status")
async def get_server_status():
    """获取服务器运行状态"""
    global _server_running, _server_pid, _server_start_time
    
    # 双重检查：如果标记为运行中但进程已不存在，修复状态
    with _server_lock:
        if _server_running and _server_pid:
            try:
                os.kill(_server_pid, 0)
            except OSError:
                _server_running = False
                _server_process = None
                _server_pid = None
                _server_start_time = None
    
    running = _server_running
    pid = _server_pid
    start_time = _server_start_time
    
    # 读取最近的日志（最后 50 行）
    recent_log = ""
    if get_server_log_file().exists():
        try:
            with open(get_server_log_file(), "r", encoding="utf-8") as f:
                lines = f.readlines()
            recent_log = "".join(lines[-50:])
        except:
            pass
    
    elapsed = ""
    if running and start_time:
        seconds = int(time.time() - start_time)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            elapsed = f"{hours}小时{minutes}分钟"
        elif minutes > 0:
            elapsed = f"{minutes}分钟{secs}秒"
        else:
            elapsed = f"{secs}秒"
    
    server_path = find_llama_server()
    
    return {
        "success": True,
        "running": running,
        "pid": pid,
        "elapsed": elapsed,
        "start_time": start_time,
        "server_path": server_path,
        "recent_log": recent_log,
    }


@router.get("/process-log")
async def get_process_log():
    """获取服务器进程日志"""
    if get_server_log_file().exists():
        try:
            with open(get_server_log_file(), "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "log": content}
        except Exception as e:
            return {"success": False, "log": "", "message": str(e)}
    return {"success": True, "log": "", "message": "暂无日志"}


@router.get("/list-models")
async def list_available_models():
    """列出软链接目录中的可用模型文件（供前端选择器使用）"""
    from config import LINKS_DIR, MODELS_DIR
    
    models = []
    
    # 从软链接目录查找
    if LINKS_DIR.exists():
        for item in sorted(LINKS_DIR.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                models.append({
                    "path": str(item),
                    "name": str(item.relative_to(LINKS_DIR)),
                    "size": item.stat().st_size,
                    "is_symlink": item.is_symlink(),
                    "source": "软链接目录",
                })
    
    # 如果软链接目录为空，直接从模型目录查找
    if not models and MODELS_DIR.exists():
        for item in sorted(MODELS_DIR.rglob("*.gguf")):
            if item.is_file():
                models.append({
                    "path": str(item),
                    "name": str(item.relative_to(MODELS_DIR)),
                    "size": item.stat().st_size,
                    "is_symlink": False,
                    "source": "模型目录",
                })
    
    return {"success": True, "models": models}
