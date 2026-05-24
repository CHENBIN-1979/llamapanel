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
        print(f"[server] \u26a0\ufe0f \u521b\u5efa\u914d\u7f6e\u76ee\u5f55\u5931\u8d25: {e}\uff0c\u5c06\u4f7f\u7528\u4e34\u65f6\u76ee\u5f55")
        import tempfile
        _CONFIG_DIR = Path(tempfile.gettempdir()) / "llamapanel_server_config"
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE = _CONFIG_DIR / "llama_server_config.json"
    _SERVER_LOG_FILE = _CONFIG_DIR / "server_process.log"
    print(f"[server] \u914d\u7f6e\u76ee\u5f55: {_CONFIG_DIR}")


def get_config_dir() -> Path:
    _ensure_config_dir()
    return _CONFIG_DIR


def get_config_file() -> Path:
    _ensure_config_dir()
    return _CONFIG_FILE


def get_server_log_file() -> Path:
    _ensure_config_dir()
    return _SERVER_LOG_FILE


# ==================== \u8bfb\u53d6 HTML \u6a21\u677f\uff08\u542b\u9519\u8bef\u5305\u5bb9\uff09 ====================
SERVER_HTML = "<h1>\u9875\u9762\u52a0\u8f7d\u5931\u8d25</h1>"
try:
    html_path = Path(__file__).parent.parent / "templates" / "server.html"
    if html_path.exists():
        with open(html_path, 'r', encoding='utf-8') as f:
            SERVER_HTML = f.read()
except Exception as e:
    print(f"[server] \u26a0\ufe0f \u8bfb\u53d6\u6a21\u677f\u5931\u8d25: {e}")
    SERVER_HTML = "<h1>\u9875\u9762\u6a21\u677f\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u6a21\u677f\u6587\u4ef6</h1>"

# ==================== llama-server \u6240\u6709\u53ef\u7528\u53c2\u6570\u5b9a\u4e49 ====================
# \u8fd9\u4e9b\u53c2\u6570\u7528\u4e8e\u524d\u7aef\u8868\u5355\u7684\u81ea\u52a8\u751f\u6210\u548c\u9a8c\u8bc1
SERVER_PARAMS_META = {
    # ===== \u6a21\u578b\u4e0e\u8def\u5f84 =====
    "model": {
        "section": "\u6a21\u578b\u4e0e\u8def\u5f84",
        "flag": "-m",
        "type": "file_picker",
        "label": "\u6a21\u578b\u6587\u4ef6\u8def\u5f84 (GGUF)",
        "description": "\u8981\u52a0\u8f7d\u7684 GGUF \u6a21\u578b\u6587\u4ef6\u8def\u5f84\u3002\u53ef\u4f7f\u7528\u8f6f\u94fe\u63a5\u76ee\u5f55\u4e2d\u7684\u6587\u4ef6\u3002",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/\u6a21\u578b\u540d\u79f0.gguf",
        "required": True,
    },
    "mmproj": {
        "section": "\u6a21\u578b\u4e0e\u8def\u5f84",
        "flag": "--mmproj",
        "type": "text",
        "label": "\u591a\u6a21\u6001\u6295\u5f71\u6587\u4ef6 (mmproj)",
        "description": "\u591a\u6a21\u6001\u6a21\u578b\u7684\u6295\u5f71\u5668\u6587\u4ef6\u8def\u5f84\uff08\u5982 LLaVA \u7b49\u89c6\u89c9\u6a21\u578b\uff09",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/\u6a21\u578b\u6587\u4ef6\u5939/mmproj-file.gguf",
    },
    "lora": {
        "section": "\u6a21\u578b\u4e0e\u8def\u5f84",
        "flag": "--lora",
        "type": "text",
        "label": "LoRA \u9002\u914d\u5668",
        "description": "LoRA \u9002\u914d\u5668\u6587\u4ef6\u8def\u5f84\uff08\u53ef\u591a\u6b21\u6307\u5b9a\uff0c\u7528\u9017\u53f7\u5206\u9694\uff09",
        "default": "",
        "placeholder": "/path/to/lora-adapter.gguf",
    },
    "lora_base": {
        "section": "\u6a21\u578b\u4e0e\u8def\u5f84",
        "flag": "--lora-base",
        "type": "text",
        "label": "LoRA \u57fa\u5ea7\u6a21\u578b",
        "description": "\u7528\u4e8e LoRA \u7684\u53ef\u9009\u57fa\u5ea7\u6a21\u578b\u8def\u5f84",
        "default": "",
        "placeholder": "/path/to/base-model.gguf",
    },

    # ===== GPU \u4e0e\u52a0\u901f =====
    "n_gpu_layers": {
        "section": "GPU \u4e0e\u52a0\u901f",
        "flag": "-ngl",
        "type": "number",
        "label": "GPU \u5c42\u6570 (-ngl)",
        "description": "\u5378\u8f7d\u5230 GPU \u7684\u5c42\u6570\u3002\u8bbe\u4e3a -1 \u8868\u793a\u5168\u90e8\u5c42\u90fd\u4f7f\u7528 GPU\u3002\u8bbe\u4e3a 0 \u8868\u793a\u7eaf CPU\u3002",
        "default": "0",
        "placeholder": "0",
        "min": -1,
        "max": 999,
    },
    "no_kv_offload": {
        "section": "GPU \u4e0e\u52a0\u901f",
        "flag": "--no-kv-offload",
        "type": "checkbox",
        "label": "\u7981\u7528 KV Cache GPU \u5378\u8f7d",
        "description": "\u7981\u7528 KV \u7f13\u5b58\u5230 GPU \u7684\u5378\u8f7d\uff08\u5b9e\u9a8c\u6027\u529f\u80fd\uff09",
        "default": False,
    },
    "tensor_split": {
        "section": "GPU \u4e0e\u52a0\u901f",
        "flag": "-ts",
        "type": "text",
        "label": "\u5f20\u91cf\u62c6\u5206\u6bd4\u4f8b",
        "description": "\u591a GPU \u65f6\u5f20\u91cf\u62c6\u5206\u6bd4\u4f8b\uff0c\u7528\u9017\u53f7\u5206\u9694\uff08\u5982: 2,1 \u8868\u793a GPU0:GPU1=2:1\uff09",
        "default": "",
        "placeholder": "2,1",
    },
    "mlock": {
        "section": "GPU \u4e0e\u52a0\u901f",
        "flag": "--mlock",
        "type": "checkbox",
        "label": "\u9501\u5b9a\u6a21\u578b\u5230\u5185\u5b58 (mlock)",
        "description": "\u5c06\u6a21\u578b\u9501\u5b9a\u5728\u7269\u7406\u5185\u5b58\u4e2d\uff0c\u9632\u6b62\u88ab\u4ea4\u6362\u5230\u78c1\u76d8\u3002\u53ef\u63d0\u9ad8\u6027\u80fd\u4f46\u5360\u7528\u66f4\u591a\u5185\u5b58\u3002",
        "default": False,
    },
    "no_mmap": {
        "section": "GPU \u4e0e\u52a0\u901f",
        "flag": "--no-mmap",
        "type": "checkbox",
        "label": "\u7981\u7528\u5185\u5b58\u6620\u5c04 (no-mmap)",
        "description": "\u7981\u7528 mmap() \u52a0\u8f7d\u6a21\u578b\u3002\u5bf9\u4e8e\u67d0\u4e9b\u7f51\u7edc\u6587\u4ef6\u7cfb\u7edf\u6216\u7279\u6b8a\u9700\u6c42\u65f6\u4f7f\u7528\u3002",
        "default": False,
    },

    # ===== \u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58 =====
    "ctx_size": {
        "section": "\u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58",
        "flag": "-c",
        "type": "number",
        "label": "\u4e0a\u4e0b\u6587\u5927\u5c0f (ctx-size)",
        "description": "Token \u4e0a\u4e0b\u6587\u7a97\u53e3\u5927\u5c0f\u3002\u8d8a\u5927\u53ef\u8bb0\u4f4f\u66f4\u591a\u5bf9\u8bdd\u5185\u5bb9\uff0c\u4f46\u6d88\u8017\u66f4\u591a\u663e\u5b58/\u5185\u5b58\u3002",
        "default": "4096",
        "placeholder": "4096",
        "min": 128,
        "max": 999999,
        "step": 128,
    },
    "rope_freq_base": {
        "section": "\u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58",
        "flag": "--rope-freq-base",
        "type": "number",
        "label": "RoPE \u9891\u7387\u57fa\u6570",
        "description": "RoPE \u9891\u7387\u57fa\u6570\u3002\u9ed8\u8ba4 10000.0\uff0c\u8c03\u6574\u53ef\u5f71\u54cd\u8fdc\u8ddd\u79bb\u4f4d\u7f6e\u7f16\u7801\u6548\u679c\u3002",
        "default": "",
        "placeholder": "10000.0",
        "min": 1,
        "max": 99999999,
        "step": 0.1,
    },
    "rope_freq_scale": {
        "section": "\u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58",
        "flag": "--rope-freq-scale",
        "type": "number",
        "label": "RoPE \u9891\u7387\u7f29\u653e",
        "description": "RoPE \u9891\u7387\u7f29\u653e\u56e0\u5b50\u3002NTK-aware \u7f29\u653e\uff0c\u9ed8\u8ba4 1.0\u3002",
        "default": "",
        "placeholder": "1.0",
        "min": 0.01,
        "max": 100,
        "step": 0.01,
    },
    "yarn_ext_factor": {
        "section": "\u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58",
        "flag": "--yarn-ext-factor",
        "type": "number",
        "label": "YaRN \u7f29\u653e\u56e0\u5b50",
        "description": "YaRN \u7f29\u653e\u56e0\u5b50\u3002\u5f53\u4f7f\u7528 YaRN \u65b9\u6cd5\u62d3\u5c55\u4e0a\u4e0b\u6587\u65f6\u8bbe\u7f6e\u6b64\u503c\u3002",
        "default": "",
        "placeholder": "1.0",
        "min": 0.01,
        "max": 100,
        "step": 0.01,
    },

    # ===== \u91c7\u6837\u53c2\u6570 =====
    "temperature": {
        "section": "\u91c7\u6837\u53c2\u6570",
        "flag": "--temp",
        "type": "number",
        "label": "Temperature",
        "description": "\u751f\u6210\u7684\u6e29\u5ea6\u53c2\u6570\u3002\u503c\u8d8a\u9ad8\u8f93\u51fa\u8d8a\u968f\u673a\uff08\u521b\u610f\uff09\uff0c\u503c\u8d8a\u4f4e\u8f93\u51fa\u8d8a\u786e\u5b9a\uff08\u51c6\u786e\uff09\u3002",
        "default": "0.8",
        "placeholder": "0.8",
        "min": 0.0,
        "max": 5.0,
        "step": 0.01,
    },
    "top_k": {
        "section": "\u91c7\u6837\u53c2\u6570",
        "flag": "--top-k",
        "type": "number",
        "label": "Top-K",
        "description": "\u4ec5\u4ece\u6a82\u7387\u6700\u9ad8\u7684 K \u4e2a token \u4e2d\u9009\u62e9\u3002\u9ed8\u8ba4 40\u30020=\u7981\u7528\u3002",
        "default": "40",
        "placeholder": "40",
        "min": 0,
        "max": 1000,
    },
    "top_p": {
        "section": "\u91c7\u6837\u53c2\u6570",
        "flag": "--top-p",
        "type": "number",
        "label": "Top-P (nucleus)",
        "description": "Nucleus \u91c7\u6837\u3002\u7d2f\u79ef\u6a82\u7387\u8fbe\u5230 P \u65f6\u505c\u6b62\u9009\u62e9 token\u3002\u9ed8\u8ba4 0.95\u3002",
        "default": "0.95",
        "placeholder": "0.95",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    "min_p": {
        "section": "\u91c7\u6837\u53c2\u6570",
        "flag": "--min-p",
        "type": "number",
        "label": "Min-P",
        "description": "\u6700\u5c0f\u6a82\u7387\u3002token \u6a82\u7387\u5c11\u4e8e (max_prob * min_p) \u7684\u88ab\u8fc7\u6ee4\u3002\u9ed8\u8ba4 0.05\u3002",
        "default": "0.05",
        "placeholder": "0.05",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
    },
    "repeat_penalty": {
        "section": "\u91c7\u6837\u53c2\u6570",
        "flag": "--repeat-penalty",
        "type": "number",
        "label": "\u91cd\u590d\u60e9\u7f5a",
        "description": "\u91cd\u590d\u60e9\u7f5a\u7cfb\u6570\u3002>1.0 \u51cf\u5c11\u91cd\u590d\uff0c<1.0 \u589e\u52a0\u91cd\u590d\u3002\u9ed8\u8ba4 1.1\u3002",
        "default": "1.1",
        "placeholder": "1.1",
        "min": 0.0,
        "max": 10.0,
        "step": 0.01,
    },

    # ===== \u670d\u52a1\u5668\u8bbe\u7f6e =====
    "host": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "--host",
        "type": "text",
        "label": "\u670d\u52a1\u5668 Host",
        "description": "\u670d\u52a1\u5668\u7ed1\u5b9a\u7684 IP \u5730\u5740\u3002\u9ed8\u8ba4 127.0.0.1\uff0c\u8bbe\u4e3a 0.0.0.0 \u53ef\u5f00\u653e\u5916\u7f51\u8bbf\u95ee\u3002",
        "default": "127.0.0.1",
        "placeholder": "127.0.0.1",
    },
    "port": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "--port",
        "type": "number",
        "label": "\u670d\u52a1\u5668\u7aef\u53e3",
        "description": "llama-server OpenAI \u517c\u5bb9 API \u7aef\u53e3\u3002\u9ed8\u8ba4 8080\u3002",
        "default": "8080",
        "placeholder": "8080",
        "min": 1,
        "max": 65535,
    },
    "timeout": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "--timeout",
        "type": "number",
        "label": "\u8bf7\u6c42\u8d85\u65f6 (\u79d2)",
        "description": "\u5ba2\u6237\u7aef\u8bf7\u6c42\u8d85\u65f6\u65f6\u95f4\uff0c\u5355\u4f4d\u79d2\u3002\u9ed8\u8ba4 0\uff08\u4e0d\u8d85\u65f6\uff09\u3002",
        "default": "0",
        "placeholder": "0",
        "min": 0,
        "max": 999999,
    },
    "n_parallel": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "-np",
        "type": "number",
        "label": "\u5e76\u53d1\u5e8f\u5217\u6570 (n-parallel)",
        "description": "\u53ef\u540c\u65f6\u5904\u7406\u7684\u5e76\u53d1\u5e8f\u5217\u6570\u3002\u6bcf\u4e2a\u5e8f\u5217\u72ec\u7acb\u7ba1\u7406\u4e0a\u4e0b\u6587\u3002",
        "default": "1",
        "placeholder": "1",
        "min": 1,
        "max": 999,
    },
    "cont_batching": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "--cont-batching",
        "type": "checkbox",
        "label": "\u5f00\u542f\u6301\u7eed\u6279\u5904\u7406",
        "description": "\u5f00\u542f\u6301\u7eed\u6279\u5904\u7406\uff0c\u63d0\u9ad8\u591a\u5e8f\u5217\u573a\u666f\u4e0b\u7684\u541e\u5410\u91cf\u3002",
        "default": False,
    },
    "embedding": {
        "section": "\u670d\u52a1\u5668\u8bbe\u7f6e",
        "flag": "--embedding",
        "type": "checkbox",
        "label": "\u5f00\u542f Embedding \u6a21\u5f0f",
        "description": "\u542f\u7528 Embedding \u63a5\u53e3\uff0c\u5141\u8bb8\u83b7\u53d6 token \u5d4c\u5165\u5411\u91cf\u3002",
        "default": False,
    },

    # ===== \u7ebf\u7a0b\u4e0e\u6027\u80fd =====
    "threads": {
        "section": "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
        "flag": "-t",
        "type": "number",
        "label": "\u751f\u6210\u7ebf\u7a0b\u6570",
        "description": "Token \u751f\u6210\u9636\u6bb5\u4f7f\u7528\u7684\u7ebf\u7a0b\u6570\u3002\u4e00\u822c\u8bbe\u4e3a CPU \u7269\u7406\u6838\u5fc3\u6570\u3002",
        "default": "8",
        "placeholder": "8",
        "min": 1,
        "max": 256,
    },
    "threads_batch": {
        "section": "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
        "flag": "--threads-batch",
        "type": "number",
        "label": "\u6279\u5904\u7406\u7ebf\u7a0b\u6570",
        "description": "Prompt \u6279\u5904\u7406\u9636\u6bb5\u4f7f\u7528\u7684\u7ebf\u7a0b\u6570\u3002\u7559\u7a7a\u5219\u4e0e\u751f\u6210\u7ebf\u7a0b\u6570\u76f8\u540c\u3002",
        "default": "",
        "placeholder": "\u7559\u7a7a\u5219\u7b49\u4e8e\u751f\u6210\u7ebf\u7a0b\u6570",
        "min": 1,
        "max": 256,
    },
    "batch_size": {
        "section": "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
        "flag": "-b",
        "type": "number",
        "label": "\u6279\u5904\u7406\u5927\u5c0f (batch-size)",
        "description": "Prompt \u5904\u7406\u7684\u6279\u5904\u7406 token \u6570\u3002\u8d8a\u5927\u8d8a\u5feb\u4f46\u6d88\u8017\u66f4\u591a\u5185\u5b58\u3002",
        "default": "2048",
        "placeholder": "2048",
        "min": 32,
        "max": 999999,
    },
    "ubatch_size": {
        "section": "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
        "flag": "-ub",
        "type": "number",
        "label": "\u7269\u7406\u6279\u5904\u7406\u5927\u5c0f (ubatch-size)",
        "description": "\u7269\u7406\u6279\u5904\u7406\u5927\u5c0f\u3002\u5f71\u54cd\u8ba1\u7b97\u6548\u7387\u3002\u4e00\u822c \u2264 batch-size\u3002",
        "default": "512",
        "placeholder": "512",
        "min": 32,
        "max": 999999,
    },
    "flash_attn": {
        "section": "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
        "flag": "--flash-attn",
        "type": "checkbox",
        "label": "\u542f\u7528 Flash Attention",
        "description": "\u4f7f\u7528 Flash Attention \u52a0\u901f\u8ba1\u7b97\uff0c\u51cf\u5c11\u663e\u5b58\u5360\u7528\u3002\u9700\u8981\u6a21\u578b\u652f\u6301\u3002",
        "default": False,
    },
}

# \u6309\u5206\u533a\u6392\u5e8f\u7684\u53c2\u6570\u5217\u8868
SERVER_PARAMS_SECTIONS = [
    "\u6a21\u578b\u4e0e\u8def\u5f84",
    "GPU \u4e0e\u52a0\u901f",
    "\u4e0a\u4e0b\u6587\u4e0e\u5185\u5b58",
    "\u91c7\u6837\u53c2\u6570",
    "\u670d\u52a1\u5668\u8bbe\u7f6e",
    "\u7ebf\u7a0b\u4e0e\u6027\u80fd",
]

# ==================== \u8f85\u52a9\u51fd\u6570 ====================


def find_llama_server() -> Optional[str]:
    """\u67e5\u627e llama-server \u53ef\u6267\u884c\u6587\u4ef6\u8def\u5f84"""
    from config import BUILD_DIR, LLAMA_DIR

    candidates = [
        BUILD_DIR / "bin" / "llama-server",
        BUILD_DIR / "llama-server",
        LLAMA_DIR / "llama-server",
    ]
    # \u4e5f\u5c1d\u8bd5\u5728 PATH \u4e2d\u67e5\u627e
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
    """\u83b7\u53d6\u9ed8\u8ba4\u914d\u7f6e"""
    config = {}
    for key, meta in SERVER_PARAMS_META.items():
        config[key] = meta["default"]
    return config


def load_config() -> Dict[str, Any]:
    """\u4ece\u6587\u4ef6\u52a0\u8f7d\u5df2\u4fdd\u5b58\u7684\u914d\u7f6e"""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # \u5408\u5e76\u9ed8\u8ba4\u503c\uff0c\u786e\u4fdd\u65b0\u589e\u53c2\u6570\u4e5f\u6709\u503c
            defaults = get_default_config()
            defaults.update(saved)
            return defaults
        except Exception as e:
            print(f"[server] \u52a0\u8f7d\u914d\u7f6e\u5931\u8d25: {e}")
    return get_default_config()


def save_config(config: Dict[str, Any]) -> bool:
    """\u4fdd\u5b58\u914d\u7f6e\u5230\u6587\u4ef6"""
    try:
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(get_config_file(), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[server] \u4fdd\u5b58\u914d\u7f6e\u5931\u8d25: {e}")
        return False


def build_command(config: Dict[str, Any]) -> list:
    """\u6839\u636e\u914d\u7f6e\u6784\u5efa llama-server \u547d\u4ee4\u884c\u53c2\u6570"""
    server_path = find_llama_server()
    if not server_path:
        raise FileNotFoundError("\u672a\u627e\u5230 llama-server \u53ef\u6267\u884c\u6587\u4ef6\uff0c\u8bf7\u5148\u7f16\u8bd1 llama.cpp")

    cmd = [server_path]

    for key, meta in SERVER_PARAMS_META.items():
        value = config.get(key, meta["default"])

        # \u8df3\u8fc7\u7a7a\u503c\uff08\u975e\u5fc5\u586b\u7684\u6587\u672c\u5b57\u6bb5\uff09
        if value is None or value == "":
            continue

        # \u8df3\u8fc7\u5047\u503c\uff08checkbox \u672a\u9009\u4e2d\uff09
        if meta["type"] == "checkbox":
            if value is True or value == "true":
                cmd.append(meta["flag"])
            continue

        # \u6570\u5b57\u548c\u6587\u672c\u503c
        cmd.append(meta["flag"])
        cmd.append(str(value))

    return cmd


def write_server_log(message: str):
    """\u5199\u5165\u670d\u52a1\u5668\u8fdb\u7a0b\u65e5\u5fd7"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(f"[server] {log_msg}")
    try:
        log_file = get_server_log_file()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"[server] \u5199\u5165\u65e5\u5fd7\u5931\u8d25: {e}")


def server_process_runner(cmd: list):
    """\u5728\u540e\u53f0\u7ebf\u7a0b\u4e2d\u8fd0\u884c llama-server \u8fdb\u7a0b"""
    global _server_process, _server_running, _server_start_time, _server_pid

    write_server_log(f"\ud83d\ude80 \u542f\u52a8\u547d\u4ee4: {' '.join(cmd)}")

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

        write_server_log(f"\u2705 \u670d\u52a1\u5668\u5df2\u542f\u52a8\uff0cPID: {process.pid}")

        # \u5b9e\u65f6\u8bfb\u53d6\u8f93\u51fa
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
            write_server_log(f"\u2705 \u670d\u52a1\u5668\u6b63\u5e38\u9000\u51fa")
        else:
            write_server_log(f"\u26a0\ufe0f \u670d\u52a1\u5668\u5f02\u5e38\u9000\u51fa\uff0c\u8fd4\u56de\u7801: {returncode}")

    except Exception as e:
        write_server_log(f"\u274c \u670d\u52a1\u5668\u8fd0\u884c\u5f02\u5e38: {e}")
        with _server_lock:
            _server_running = False
            _server_process = None
            _server_pid = None


# ==================== API \u7aef\u70b9 ====================


@router.get("/page", response_class=HTMLResponse)
async def server_page():
    """\u670d\u52a1\u5668\u53c2\u6570\u914d\u7f6e\u9875\u9762"""
    return HTMLResponse(content=SERVER_HTML)


@router.get("/params-meta")
async def get_params_meta():
    """\u83b7\u53d6\u6240\u6709\u53c2\u6570\u5143\u6570\u636e\uff08\u524d\u7aef\u7528\u4e8e\u52a8\u6001\u6e32\u67d3\u8868\u5355\uff09"""
    return {
        "success": True,
        "params": SERVER_PARAMS_META,
        "sections": SERVER_PARAMS_SECTIONS,
    }


@router.get("/config")
async def get_config():
    """\u83b7\u53d6\u5df2\u4fdd\u5b58\u7684\u670d\u52a1\u5668\u914d\u7f6e"""
    config = load_config()
    return {"success": True, "config": config}


@router.post("/config")
async def set_config(payload: dict = Body(...)):
    """\u4fdd\u5b58\u670d\u52a1\u5668\u914d\u7f6e"""
    config = payload.get("config", {})
    if not config:
        return {"success": False, "message": "\u914d\u7f6e\u6570\u636e\u4e3a\u7a7a"}

    if save_config(config):
        return {"success": True, "message": "\u914d\u7f6e\u5df2\u4fdd\u5b58"}
    else:
        return {"success": False, "message": "\u914d\u7f6e\u4fdd\u5b58\u5931\u8d25"}


@router.post("/start")
async def start_server():
    """\u542f\u52a8 llama-server"""
    global _server_running

    # \u68c0\u67e5\u662f\u5426\u5df2\u5728\u8fd0\u884c
    with _server_lock:
        if _server_running:
            return {"success": False, "message": "\u670d\u52a1\u5668\u5df2\u5728\u8fd0\u884c\u4e2d"}

    # \u67e5\u627e llama-server
    server_path = find_llama_server()
    if not server_path:
        return {"success": False, "message": "\u672a\u627e\u5230 llama-server \u53ef\u6267\u884c\u6587\u4ef6\u3002\u8bf7\u5148\u5728\u4e3b\u9875\u4e2d\u7f16\u8bd1 llama.cpp\u3002"}

    # \u52a0\u8f7d\u914d\u7f6e\u5e76\u6784\u5efa\u547d\u4ee4
    config = load_config()

    # \u68c0\u67e5\u6a21\u578b\u6587\u4ef6
    model_path = config.get("model", "")
    if not model_path:
        return {"success": False, "message": "\u8bf7\u5148\u914d\u7f6e\u6a21\u578b\u6587\u4ef6\u8def\u5f84 (-m)"}

    if not os.path.exists(model_path):
        return {"success": False, "message": f"\u6a21\u578b\u6587\u4ef6\u4e0d\u5b58\u5728: {model_path}"}

    try:
        cmd = build_command(config)
    except FileNotFoundError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"\u6784\u5efa\u547d\u4ee4\u5931\u8d25: {e}"}

    # \u6e05\u7a7a\u65e7\u65e5\u5fd7
    try:
        if get_server_log_file().exists():
            get_server_log_file().unlink()
    except:
        pass

    write_server_log("=" * 60)
    write_server_log("\u914d\u7f6e\u53c2\u6570:")
    for key, meta in SERVER_PARAMS_META.items():
        val = config.get(key, "")
        if val is not None and str(val).strip():
            write_server_log(f"  {meta['flag']} {meta['label']}: {val}")
    write_server_log("=" * 60)

    # \u5728\u540e\u53f0\u7ebf\u7a0b\u542f\u52a8\u670d\u52a1\u5668
    thread = threading.Thread(target=server_process_runner, args=(cmd,), daemon=True)
    thread.start()

    # \u7b49\u5f85\u4e00\u5c0f\u6bb5\u65f6\u95f4\u68c0\u67e5\u662f\u5426\u542f\u52a8\u6210\u529f
    time.sleep(1)

    with _server_lock:
        if _server_running:
            return {
                "success": True,
                "message": f"\u670d\u52a1\u5668\u5df2\u542f\u52a8 (PID: {_server_pid})",
                "pid": _server_pid,
            }
        else:
            # \u53ef\u80fd\u542f\u52a8\u5931\u8d25\uff0c\u8bfb\u53d6\u65e5\u5fd7
            log_content = ""
            try:
                if get_server_log_file().exists():
                    with open(get_server_log_file(), "r", encoding="utf-8") as f:
                        log_content = f.read()
            except:
                pass
            return {
                "success": False,
                "message": "\u670d\u52a1\u5668\u542f\u52a8\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u65e5\u5fd7\u4e86\u89e3\u8be6\u60c5",
                "log": log_content[-1000:] if log_content else "",
            }


@router.post("/stop")
async def stop_server():
    """\u505c\u6b62 llama-server \u8fdb\u7a0b"""
    global _server_process, _server_running, _server_pid

    with _server_lock:
        if not _server_running or _server_process is None:
            return {"success": False, "message": "\u670d\u52a1\u5668\u672a\u5728\u8fd0\u884c"}

        pid = _server_pid
        process = _server_process

    write_server_log(f"\ud83d\uded1 \u6b63\u5728\u505c\u6b62\u670d\u52a1\u5668 (PID: {pid})...")

    try:
        # \u5148\u53d1 SIGTERM \u4fe1\u53f7\u4f18\u96c5\u9000\u51fa
        os.kill(pid, signal.SIGTERM)

        # \u7b49\u5f85\u6700\u591a 10 \u79d2
        for _ in range(20):
            time.sleep(0.5)
            if not _server_running:
                break
            # \u68c0\u67e5\u8fdb\u7a0b\u662f\u5426\u8fd8\u6d3b\u7740
            try:
                os.kill(pid, 0)  # \u4fe1\u53f7 0 \u4ec5\u68c0\u67e5\u8fdb\u7a0b\u662f\u5426\u5b58\u5728
            except OSError:
                with _server_lock:
                    _server_running = False
                    _server_process = None
                    _server_pid = None
                break
        else:
            # \u5982\u679c 10 \u79d2\u540e\u8fd8\u6ca1\u7ed3\u675f\uff0c\u5f3a\u884c\u6740\u6b7b
            write_server_log("\u26a0\ufe0f \u8fdb\u7a0b\u672a\u54cd\u5e94 SIGTERM\uff0c\u53d1\u9001 SIGKILL...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
    except ProcessLookupError:
        pass
    except Exception as e:
        write_server_log(f"\u274c \u505c\u6b62\u670d\u52a1\u5668\u5931\u8d25: {e}")
        return {"success": False, "message": f"\u505c\u6b62\u5931\u8d25: {e}"}

    with _server_lock:
        _server_running = False
        _server_process = None
        _server_pid = None

    write_server_log("\u2705 \u670d\u52a1\u5668\u5df2\u505c\u6b62")
    return {"success": True, "message": "\u670d\u52a1\u5668\u5df2\u505c\u6b62"}


@router.get("/status")
async def get_server_status():
    """\u83b7\u53d6\u670d\u52a1\u5668\u8fd0\u884c\u72b6\u6001"""
    global _server_running, _server_pid, _server_start_time

    # \u53cc\u91cd\u68c0\u67e5\uff1a\u5982\u679c\u6807\u8bb0\u4e3a\u8fd0\u884c\u4e2d\u4f46\u8fdb\u7a0b\u5df2\u4e0d\u5b58\u5728\uff0c\u4fee\u590d\u72b6\u6001
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

    # \u8bfb\u53d6\u6700\u8fd1\u7684\u65e5\u5fd7\uff08\u6700\u540e 50 \u884c\uff09
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
            elapsed = f"{hours}\u5c0f\u65f6{minutes}\u5206\u949f"
        elif minutes > 0:
            elapsed = f"{minutes}\u5206\u949f{secs}\u79d2"
        else:
            elapsed = f"{secs}\u79d2"

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
    """\u83b7\u53d6\u670d\u52a1\u5668\u8fdb\u7a0b\u65e5\u5fd7"""
    if get_server_log_file().exists():
        try:
            with open(get_server_log_file(), "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "log": content}
        except Exception as e:
            return {"success": False, "log": "", "message": str(e)}
    return {"success": True, "log": "", "message": "\u6682\u65e0\u65e5\u5fd7"}


@router.get("/list-models")
async def list_available_models():
    """\u5217\u51fa\u8f6f\u94fe\u63a5\u76ee\u5f55\u4e2d\u7684\u53ef\u7528\u6a21\u578b\u6587\u4ef6\uff08\u4f9b\u524d\u7aef\u9009\u62e9\u5668\u4f7f\u7528\uff09"""
    from config import LINKS_DIR, MODELS_DIR

    models = []

    # \u4ece\u8f6f\u94fe\u63a5\u76ee\u5f55\u67e5\u627e
    if LINKS_DIR.exists():
        for item in sorted(LINKS_DIR.rglob("*")):
            if item.is_file() and not item.name.startswith("."):
                models.append({
                    "path": str(item),
                    "name": str(item.relative_to(LINKS_DIR)),
                    "size": item.stat().st_size,
                    "is_symlink": item.is_symlink(),
                    "source": "\u8f6f\u94fe\u63a5\u76ee\u5f55",
                })

    # \u5982\u679c\u8f6f\u94fe\u63a5\u76ee\u5f55\u4e3a\u7a7a\uff0c\u76f4\u63a5\u4ece\u6a21\u578b\u76ee\u5f55\u67e5\u627e
    if not models and MODELS_DIR.exists():
        for item in sorted(MODELS_DIR.rglob("*.gguf")):
            if item.is_file():
                models.append({
                    "path": str(item),
                    "name": str(item.relative_to(MODELS_DIR)),
                    "size": item.stat().st_size,
                    "is_symlink": False,
                    "source": "\u6a21\u578b\u76ee\u5f55",
                })

    return {"success": True, "models": models}
