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

def get_models_ini_path() -> Path:
    """获取 models.ini 多模型配置文件路径"""
    _ensure_config_dir()
    return _CONFIG_DIR / "models.ini"

def get_config_ini_path() -> Path:
    """获取 config.ini 总配置文件路径"""
    _ensure_config_dir()
    return _CONFIG_DIR / "config.ini"

# ==================== 读取 HTML 模板（含错误包容） ====================
PARAMS_HTML = "<h1>页面加载失败</h1>"
SERVER_SETTINGS_HTML = "<h1>页面加载失败</h1>"
ADD_MODEL_POPUP_HTML = "<h1>添加模型弹窗加载失败</h1>"
try:
    base_path = Path(__file__).parent.parent / "templates"
    # 参数配置页面
    params_path = base_path / "params.html"
    if params_path.exists():
        with open(params_path, 'r', encoding='utf-8') as f:
            PARAMS_HTML = f.read()
    # 服务器设置页面（llama.cpp Server）
    settings_path = base_path / "server_settings.html"
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            SERVER_SETTINGS_HTML = f.read()
    # 弹窗页面（添加模型）
    popup_path = base_path / "add_model_popup.html"
    if popup_path.exists():
        with open(popup_path, 'r', encoding='utf-8') as f:
            ADD_MODEL_POPUP_HTML = f.read()
except Exception as e:
    print(f"[server] ⚠️ 读取模板失败: {e}")
    ADD_MODEL_POPUP_HTML = "<h1>添加模型弹窗加载失败</h1>"

# ==================== llama-server 所有可用参数定义 ====================
# 这些参数用于前端表单的自动生成和验证
SERVER_PARAMS_META = {
    # ===== 模型与路径 =====
    "model": {
        "section": "模型与路径",
        "flag": "-m",
        "type": "file_picker",
        "label": "模型文件路径 (GGUF)",
        "description": "📄 选择你要用来聊天的 AI 模型文件（.gguf 格式）。可以点击下方的「浏览已下载模型」按钮快速选择，也可以手动输入路径。这是必填项，不填就没法启动 AI 服务。",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/模型名称.gguf",
        "required": True,
        "ref_scenario": "推荐使用 Q4_K_M 或 Q5_K_M 量化等级的 GGUF 文件，在质量和性能间取得平衡",
    },
    "mmproj": {
        "section": "模型与路径",
        "flag": "--mmproj",
        "type": "file_picker",
        "label": "多模态投影文件 (mmproj)",
        "description": "🖼️ 如果你用的是「能看懂图片」的模型（如 LLaVA 等多模态模型），需要额外指定这个文件。纯文本模型不需要，保持为空即可（不会添加到启动命令中）。",
        "default": "",
        "placeholder": "/data/llamapanel/model_links/模型文件夹/mmproj-file.gguf",
        "ref_scenario": "只有多模态模型（如 LLaVA、Qwen-VL）才需要填此项，纯文本模型请保持为空",
    },
    "lora": {
        "section": "模型与路径",
        "flag": "--lora",
        "type": "text",
        "label": "LoRA 适配器",
        "description": "🎯 LoRA 补丁文件路径。LoRA 像一个「技能插件」，让 AI 学会特定技能（如编程、写特定风格），而不用重新训练整个大模型。如果你没有 LoRA 文件，请保持为空（不会添加到启动命令中）。多个补丁用逗号分隔，例如：/path/lora1.gguf,/path/lora2.gguf",
        "default": "",
        "placeholder": "/path/to/lora-adapter.gguf",
    },
    "lora_base": {
        "section": "模型与路径",
        "flag": "--lora-base",
        "type": "text",
        "label": "LoRA 基座模型",
        "description": "🧩 某些 LoRA 补丁需要搭配一个「基础模型」一起使用。如果你不清楚或上面的 LoRA 补丁没要求，请保持为空（不会添加到启动命令中）。只有当你使用的 LoRA 明确要求基座模型时才需要填。",
        "default": "",
        "placeholder": "/path/to/base-model.gguf",
    },

    # ===== GPU 与加速 =====
    "n_gpu_layers": {
        "section": "GPU 与加速",
        "flag": "-ngl",
        "type": "number",
        "label": "GPU 加速层数 (-ngl)",
        "description": "🎮 把AI模型的多少层「搬」到显卡上跑。显卡跑得特快，所以层数越多速度越快！但显卡显存有限，层数太多可能放不下。\n• -1 = 全部用显卡（最快，但需要大显存）\n• 0 = 只用CPU（最慢，但不耗显存）\n• 建议：先试 -1，如果启动时报显存不足，就慢慢减少，直到能正常运行为止。",
        "default": "0",
        "placeholder": "0",
        "min": -1,
        "max": 999,
        "ref_scenario": "大显存显卡(>=12GB)→-1（全速），中小显存(4~8GB)→20~40，无显卡/显存不足→0（纯CPU）",
    },
    "no_kv_offload": {
        "section": "GPU 与加速",
        "flag": "--no-kv-offload",
        "type": "checkbox",
        "label": "禁用 KV 缓存 GPU 加速",
        "description": "🧠 KV 缓存是AI的「短期记忆」。默认情况下这部分记忆也放在显卡上加速访问。开启此选项后，短期记忆改用CPU内存，能省下一些显存，但速度会变慢。",
        "ref_scenario": "显存不够用时开启，正常情况下保持关闭",
        "default": False,
    },
    "cache_type_k": {
        "section": "GPU 与加速",
        "flag": "--cache-type-k",
        "type": "select",
        "label": "K 缓存压缩类型",
        "description": "🗜️ 给AI的「短期记忆」做压缩，省显存！就像把行李用真空袋压缩，能装更多，但存取会慢一丢丢。\\n• f16 = 不压缩，速度最快但最占显存\\n• q8_0 = 8位压缩，省一半显存，速度影响很小（推荐）\\n• q4_0 = 4位超级压缩，最省显存但精度略降",
        "default": "f16",
        "options": [
            {"value": "f16", "label": "f16 (不压缩，最快)"},
            {"value": "q4_0", "label": "q4_0 (4位压缩，最省显存)"},
            {"value": "q8_0", "label": "q8_0 (8位压缩，均衡推荐)"},
            {"value": "q4_1", "label": "q4_1 (4位压缩+v，略好于q4_0)"},
        ],
        "ref_scenario": "显存充裕选 f16，显存紧张选 q8_0，非常紧张选 q4_0",
    },
    "cache_type_v": {
        "section": "GPU 与加速",
        "flag": "--cache-type-v",
        "type": "select",
        "label": "V 缓存压缩类型",
        "description": "🗜️ 同样是给AI「短期记忆」做压缩，但压缩的是另一部分（Value缓存）。和上面的K缓存配合使用效果更好。\\n• f16 = 不压缩\\n• q4_0 = 4位超级压缩，比上面的K缓存省得更多",
        "default": "f16",
        "options": [
            {"value": "f16", "label": "f16 (不压缩，最快)"},
            {"value": "q4_0", "label": "q4_0 (4位压缩，最省显存)"},
            {"value": "q8_0", "label": "q8_0 (8位压缩，均衡推荐)"},
            {"value": "q4_1", "label": "q4_1 (4位压缩+v，略好于q4_0)"},
        ],
        "ref_scenario": "一般和K缓存选一样的类型，想最大限度省显存都选 q4_0",
    },
    "no_unload": {
        "section": "GPU 与加速",
        "flag": "--no-unload",
        "type": "checkbox",
        "label": "模型常驻 GPU 显存",
        "description": "💾 开启后AI模型推理完也不从显卡上「搬走」，一直留在显存里。下次聊天就能秒回，不用重新加载。",
        "ref_scenario": "频繁使用AI时开启提升响应速度，偶尔使用时关闭释放显存",
        "default": False,
    },
    "tensor_split": {
        "section": "GPU 与加速",
        "flag": "-ts",
        "type": "text",
        "label": "多显卡分工比例",
        "description": "🖥️🖥️ 如果你装了多张显卡，这个参数告诉系统「每张卡干多少活」。比如填 2,1 表示让第一张卡干2份活，第二张卡干1份活。",
        "ref_scenario": "多张显卡才需填写，相同显卡填 1,1，按性能比例填写",
        "default": "",
        "placeholder": "如: 2,1（GPU0:GPU1=2:1）",
    },
    "mlock": {
        "section": "GPU 与加速",
        "flag": "--mlock",
        "type": "checkbox",
        "label": "锁定到物理内存",
        "description": "🔒 把AI模型「钉」在物理内存里，不让系统把它挪到硬盘上的虚拟内存（虚拟内存比物理内存慢很多倍）。可以保证AI响应速度稳定。",
        "ref_scenario": "内存比模型大至少2GB时开启，内存紧张时关闭",
        "default": False,
    },
    "no_mmap": {
        "section": "GPU 与加速",
        "flag": "--no-mmap",
        "type": "checkbox",
        "label": "禁用内存映射加载",
        "description": "🚫 换一种方式加载模型文件。正常情况下AI直接从文件「映射」到内存，省内存且启动快。但某些特殊系统（如网络硬盘、NAS）可能不支持这种方式，开启此选项改用传统方式加载。",
        "ref_scenario": "正常情况下不要开启，网络硬盘加载失败时尝试开启",
        "default": False,
    },

    # ===== 上下文与内存 =====
    "ctx_size": {
        "section": "上下文与内存",
        "flag": "-c",
        "type": "number",
        "label": "上下文大小 (ctx-size)",
        "description": "🏠 AI的\"工作台面\"大小。台面越大，AI能同时记住的对话内容就越多，但占用的显存/内存也越多。太小的话聊久了AI会\"忘记\"前面说过什么。建议根据你的显卡显存来调节。",
        "default": "4096",
        "placeholder": "4096",
        "min": 128,
        "max": 999999,
        "step": 128,
        "ref_scenario": "短对话/简单问答→2048~4096，长对话/分析长文→8192~32768，极长文本/代码生成→65536+",
    },
    "rope_freq_base": {
        "section": "上下文与内存",
        "flag": "--rope-freq-base",
        "type": "number",
        "label": "RoPE 频率基数",
        "description": "🪄 一个让AI\"打破出厂记忆限制\"的魔法数字。比如填800000.0，原本只能记4千字的模型就能记住3万多字。这是高级功能，不懂或不需要可以不填，用默认值就好。",
        "default": "",
        "placeholder": "如: 800000.0",
        "step": 0.1,
        "needs_checkbox": True,
    },
    "rope_freq_scale": {
        "section": "上下文与内存",
        "flag": "--rope-freq-scale",
        "type": "number",
        "label": "RoPE 频率缩放",
        "description": "🔬 缩小这个值能让AI的\"记忆空间\"变大。比如填0.25，原本4千字的模型就能记住1万6千字。和上面的\"频率基数\"配合使用，不懂可以不填。",
        "default": "",
        "placeholder": "如: 0.25",
        "step": 0.01,
        "needs_checkbox": True,
    },
    "rope_scaling": {
        "section": "上下文与内存",
        "flag": "--rope-scaling",
        "type": "select",
        "label": "RoPE 缩放类型",
        "description": "🔧 扩展AI记忆空间时用的\"魔法公式\"。选yarn效果更好、更先进，选linear比较传统。如果不确定，保持默认yarn即可。",
        "default": "yarn",
        "options": [
            {"value": "linear", "label": "linear (线性)"},
            {"value": "yarn", "label": "yarn (YaRN)"},
        ],
        "needs_checkbox": True,
    },
    "rope_scale": {
        "section": "上下文与内存",
        "flag": "--rope-scale",
        "type": "number",
        "label": "RoPE 上下文缩放",
        "description": "📐 记忆放大的\"倍数\"。填2.0表示让AI的记性扩大2倍。需配合上方把缩放类型选为yarn一起使用。",
        "default": "2.0",
        "placeholder": "2.0",
        "min": 0.0,
        "step": 0.5,
        "ref_scenario": "2.0（常用），1.0（不扩展），4.0（强力扩展）",
    },
    "yarn_orig_ctx": {
        "section": "上下文与内存",
        "flag": "--yarn-orig-ctx",
        "type": "number",
        "label": "YaRN 原始上下文大小",
        "description": "📏 你用的这个模型\"出厂时\"原本自带多大的记忆空间？比如你下载的模型说明上写支持32K上下文，就填32768。配合上面的\"缩放类型=yarn\"一起使用。",
        "default": "32768",
        "placeholder": "32768",
        "min": 128,
        "step": 128,
        "ref_scenario": "32768（标准32K模型），4096（标准4K模型），8192（标准8K模型）",
        "needs_checkbox": True,
    },

    # ===== 采样参数 =====
    "temp": {
        "section": "采样参数",
        "flag": "--temp",
        "type": "number",
        "label": "温度 (Temperature)",
        "description": "🎲 控制回答的\"创造力\"大小。温度越高（如1.2~1.5），AI越爱\"天马行空\"，可能用你意想不到的词；温度越低（如0.1~0.3），AI越\"循规蹈矩\"，每次回答都差不多。",
        "default": "0.8",
        "placeholder": "0.8",
        "min": 0.0,
        "max": 2.0,
        "step": 0.01,
        "ref_scenario": "写诗/创意写作→0.9~1.2，写代码/事实问答→0.1~0.3，通用聊天→0.7~0.8，调用工具→0.1~0.3",
    },
    "top_k": {
        "section": "采样参数",
        "flag": "--top-k",
        "type": "number",
        "label": "Top-K",
        "description": "🎯 每次生成时，只让AI从\"候选名单\"前K个词里挑选。比如Top-K=40，AI就只能从排名前40的词语中选择，冷门词直接被排除。K越小回答越保守，K越大越有惊喜。",
        "default": "40",
        "placeholder": "40",
        "min": 0,
        "max": 200,
        "ref_scenario": "40~60（通用），10~20（严谨回答），0（禁用），调用工具→10~20",
    },
    "top_p": {
        "section": "采样参数",
        "flag": "--top-p",
        "type": "number",
        "label": "Top-P (核采样)",
        "description": "🎯 动态\"淘汰制\"AI不断把最可能的词加起来，直到总概率达到Top-P值就停止。比如Top-P=0.9，只保留那些概率加起来占90%的词，剩下的10%冷门词全部淘汰。P越小候选词越少，回答越稳定。",
        "default": "0.95",
        "placeholder": "0.95",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "ref_scenario": "0.9~0.95（通用），0.5~0.7（严谨回答），1.0（不限制），调用工具→0.1~0.3",
    },
    "min_p": {
        "section": "采样参数",
        "flag": "--min-p",
        "type": "number",
        "label": "Min-P",
        "description": "🪝 强行\"踢掉\"冷门词。如果一个词的热门程度不到最热门词的min_p倍，就直接淘汰。比如min_p=0.05，最热门词概率30%，那概率低于1.5%的词全部出局。能有效防止AI突然\"抽风\"说出不着边际的话。",
        "default": "0.05",
        "placeholder": "0.05",
        "min": 0.0,
        "max": 1.0,
        "step": 0.01,
        "ref_scenario": "0.05~0.1（推荐），0.2（严格），0（不限制），调用工具→0.2~0.3",
    },
    "repeat_penalty": {
        "section": "采样参数",
        "flag": "--repeat-penalty",
        "type": "number",
        "label": "重复惩罚",
        "description": "🔁 防止AI变\"复读机\"的力度。值越大，AI越不敢重复刚说过的话。1.0=随便重复，1.05=轻微提醒，1.1=适度避免，1.2+=坚决不重复（但可能导致话题跳跃）。",
        "default": "1.1",
        "placeholder": "1.1",
        "min": 1.0,
        "max": 2.0,
        "step": 0.01,
        "ref_scenario": "1.0~1.05（自由聊天），1.1~1.15（通用/写作），1.15~1.2（丰富词汇），调用工具→1.0~1.05",
    },
    "repeat_last_n": {
        "section": "采样参数",
        "flag": "--repeat-last-n",
        "type": "number",
        "label": "重复惩罚窗口",
        "description": "📏 在最近多少个字的范围内检查重复。比如设为64，AI在最近64个字内重复说某词就会被扣分。设太小查重范围窄，AI可能前后翻来覆去说同一套话；设太大会\"记性太好\"，AI可能因避免旧词而跑偏。",
        "default": "64",
        "placeholder": "64",
        "min": -1,
        "max": 99999,
        "ref_scenario": "64~128（通用聊天），256+（长文创作），0（不查重），-1（全程检查），调用工具→64~128",
    },
    "presence_penalty": {
        "section": "采样参数",
        "flag": "--presence-penalty",
        "type": "number",
        "label": "存在惩罚 (presence-penalty)",
        "description": "💡 鼓励AI\"聊点新东西\"。只要一个概念出现过就会被扣分，AI就会转向没用过的新词。值越大，AI越爱引入新话题、新词汇，适合头脑风暴或创意写作。但太大可能导致回答散乱。",
        "default": "0.0",
        "placeholder": "0.0",
        "min": -2.0,
        "max": 2.0,
        "step": 0.01,
        "ref_scenario": "0.0（不干预），0.1~0.3（适当多样），0.4~0.6（强烈创新），调用工具→0.0~0.1",
    },

    # ===== 服务器设置 =====
    "host": {
        "section": "服务器设置",
        "flag": "--host",
        "type": "text",
        "label": "监听地址 (Host)",
        "description": "🌐 AI 服务开在哪个「门牌号」上。\n • 127.0.0.1 = 仅本机可用（推荐，安全省心）\n • 0.0.0.0 = 开放给局域网其他人用（比如让同一办公室的人一起访问）\n普通用户保持默认 127.0.0.1 即可。",
        "default": "127.0.0.1",
        "placeholder": "127.0.0.1",
    },
    "port": {
        "section": "服务器设置",
        "flag": "--port",
        "type": "number",
        "label": "监听端口 (Port)",
        "description": "🔌 AI 服务开在哪个「门牌号」上的具体房间号。\n • 8080 = 常用默认端口，一般不需要改\n • 如果 8080 被其他程序占用，可以换个别的数字（如 8081、8082）\n普通用户保持默认即可。",
        "default": "8080",
        "placeholder": "8080",
        "min": 1,
        "max": 65535,
    },
    "timeout": {
        "section": "服务器设置",
        "flag": "--timeout",
        "type": "number",
        "label": "模型自动卸载空闲超时 (秒)",
        "description": "⏱️ 如果开启了 GPU 加速（GPU层数>0），模型不用的时候多久后从显存里清出来，省出空间给别人用。\n • 600 秒（10分钟）= 适中，聊完天等一会儿就释放\n • 0 = 从不卸载，一直占着显存（运行最快但别人没法用）\n • 想省显存就设小一点（如 60 秒），想流畅就设大一点\n普通用户保持默认 600 即可。",
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
        "description": "👥 允许几个人同时向 AI 提问。\n • 1 = 一次只服务一个人（稳当，适合个人用）\n • 2~4 = 家人/同事一起用\n • 注意：设得越大越吃显存/内存，如果服务卡顿就改回 1\n普通用户保持默认 1 即可。",
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
        "description": "📦 开启「拼车模式」—— 当多人同时提问时，AI 把多个问题凑一批处理，效率更高。\n • 勾选 = 多人同时使用时更流畅（推荐，除非只有你一个人用）\n • 不勾选 = 一个人用完下一个人才能用，排队等待\n普通用户保持勾选即可。",
        "default": True,
    },
    "slots": {
        "section": "服务器设置",
        "flag": "--slots",
        "type": "number",
        "label": "最大 slots 数",
        "description": "🪑 相当于准备多少个「座位」给客人坐。每个座位同时服务一个请求。\n • 留空 = 自动等于上面的「并行序列数」，够用\n • 如果开启「持续批处理」且人多，可以设大一点（如等于2倍的并行数）\n普通用户留空即可。",
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
        "description": "💾 对话「记忆」存到硬盘的文件夹位置。关掉 AI 再启动后，之前的聊天记录还能找回来。\n • 留空 = 不保存，重启后对话从头开始\n • 填写路径 = 保存在指定文件夹，重启后对话还在\n这是个高级功能，普通用户留空即可。",
        "default": "",
        "placeholder": "/data/llamapanel/slot_cache",
    },
    "embeddings": {
        "section": "服务器设置",
        "flag": "--embeddings",
        "type": "checkbox",
        "label": "启用嵌入模式",
        "description": "🧩 把 AI 模型变成一个「阅读理解器」—— 不聊天，而是把文字转换成数字特征（向量）。\n • 勾选 = 配合外部程序做文本分类、搜索等（如 RAG 知识库）\n • 不勾选 = 正常聊天模式\n一般用户不需要勾选，除非你知道自己在做什么。",
        "default": False,
    },
    "no_webui": {
        "section": "服务器设置",
        "flag": "--no-webui",
        "type": "checkbox",
        "label": "禁用 WebUI",
        "description": "🚫 默认启动后会自动打开一个内置的简陋聊天页面。勾选后就不启动它了（节省资源）。\n我们有自己的漂亮聊天界面，所以这个内置页面用不上。\n建议保持不勾选（让它启动着也无妨，不碍事）。",
        "default": False,
    },
    "jinja": {
        "section": "服务器设置",
        "flag": "--jinja",
        "type": "checkbox",
        "label": "启用 Jinja2 模板",
        "description": "📝 让 AI 使用它自带的「说话模板」来组织对话。大多数新模型都有这个，能保证对话格式正确。\n • 勾选 = 让模型自己决定怎么排版对话（推荐，保持勾选）\n • 不勾选 = 用默认简单格式（可能会让回复变奇怪）\n普通用户保持勾选即可。",
        "default": True,
    },
    "mcp": {
        "section": "服务器设置",
        "flag": "--webui-mcp-proxy",
        "type": "checkbox",
        "label": "启用 WebUI MCP Proxy",
        "description": "🔌 启用 llama.cpp 内置的 WebUI MCP 代理功能，允许外部工具（如 IDE 插件）通过 MCP 协议与 AI 模型交互。\n⚠️ 注意：此功能需要较新版本的 llama.cpp 支持。如果您的 llama-server 启动报错，说明版本不支持，取消勾选即可。",
        "ref_scenario": "一般用户保持关闭。如果你在使用支持 MCP 的工具（如某些 IDE 插件），才需要开启。",
        "default": False,
    },
    # ===== 线程与性能 =====
    "threads": {
        "section": "线程与性能",
        "flag": "-t",
        "type": "number",
        "label": "生成线程数",
        "description": "⚡ AI「动脑思考」时用多少个CPU核心一起干活。核心越多算得越快，但太多反而会因内部协调变慢。一般来说设为你CPU的「物理核心数」最佳（不是虚拟线程数）。",
        "default": "8",
        "placeholder": "8",
        "min": 1,
        "max": 256,
        "ref_scenario": "查看CPU信息：Linux运行 lscpu，Windows任务管理器>性能>CPU。4核CPU→4，8核CPU→8，16核CPU→12~16（留几个核心给系统用）",
    },
    "threads_batch": {
        "section": "线程与性能",
        "flag": "--threads-batch",
        "type": "number",
        "label": "批处理线程数",
        "description": "📦 AI「阅读理解」你输入的整段话时，用多少个CPU核心来处理。如果你经常上传长篇文章让AI分析，设大一点能加快处理速度。",
        "ref_scenario": "通常保持和上面的「生成线程数」一致即可（留空会自动等于它）。如果你经常处理超长文本（几万字），可以比生成线程数多设2~4个。",
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
        "description": "📊 AI每次「阅读理解」时，一次性读多少个字（token）。读得越多，处理速度越快，但也更耗内存。就像吃自助餐，一次拿一满盘虽然快，但盘子太大可能端不动。",
        "default": "2048",
        "placeholder": "2048",
        "min": 32,
        "max": 999999,
        "ref_scenario": "普通聊天/短文本→512~2048，长文本分析→4096~8192，内存充足想要极致速度→16384+",
    },
    "ubatch_size": {
        "section": "线程与性能",
        "flag": "-ub",
        "type": "number",
        "label": "物理批处理大小 (ubatch-size)",
        "description": "🔬 AI「真正一次性处理」的字数。可以理解成上面的batch-size是「计划读多少」，而这个是「一口吃多少」。一口吃太多可能噎着（显存爆掉）。",
        "ref_scenario": "保持默认512即可。如果内存/显存充足想提提速，可以试试1024。如果报显存不足，降到256或128。一般设成 batch-size 的 1/4 左右比较稳妥。",
        "default": "512",
        "placeholder": "512",
        "min": 32,
        "max": 999999,
    },
    "flash_attn": {
        "section": "线程与性能",
        "flag": "--flash-attn",
        "type": "select",
        "label": "Flash Attention 加速",
        "description": "⚡ 一项「黑科技」优化技术，让AI推理时省显存、跑更快！就像给你的显卡开了「涡轮增压」。绝大多数现代模型都支持，开启几乎没有副作用。\n• on = 开启加速（推荐）\n• off = 关闭\n• auto = 让AI自己判断要不要开",
        "ref_scenario": "直接选「on」开启就好。如果模型不支持（启动报错），再改成 off。",
        "default": "on",
        "options": [
            {"value": "on", "label": "开启 (on) ✅ 推荐"},
            {"value": "off", "label": "关闭 (off)"},
            {"value": "auto", "label": "自动 (auto)"},
        ],
    },
    "n_cpu_moe": {
        "section": "线程与性能",
        "flag": "--n-cpu-moe",
        "type": "number",
        "label": "MoE 专家 CPU 核心数",
        "description": "🧠 针对「混合专家模型」（一种特殊AI架构，如 Mixtral、Qwen2-MoE）的加速。这类模型内部有很多「小专家」，这个参数控制用多少个CPU核心来处理这些小专家。",
        "ref_scenario": "普通模型（非MoE）保持0，MoE模型（如Mixtral 8x7B）设为CPU物理核心数（如8、16、32）",
        "default": "0",
        "placeholder": "32（Mixtral推荐值）",
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


def _sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """修复配置中的类型不匹配问题（如旧版 boolean 值与新版 select 类型冲突）"""
    for key, meta in SERVER_PARAMS_META.items():
        if key not in config:
            continue
        val = config[key]
        param_type = meta.get("type", "text")

        # 修复 1: select 类型如果存了 boolean 值，改成默认值
        if param_type == "select" and isinstance(val, bool):
            config[key] = meta["default"]
            continue

        # 修复 2: select 类型的值不在可选列表中，改成默认值
        if param_type == "select" and "options" in meta:
            valid_values = [o["value"] if isinstance(o, dict) else o for o in meta["options"]]
            if str(val) not in valid_values:
                config[key] = meta["default"]
                continue

        # 修复 3: checkbox 类型存了字符串，转成 boolean
        if param_type == "checkbox":
            if isinstance(val, str):
                config[key] = val.lower() in ("true", "1", "yes", "on")
                continue
            if isinstance(val, int):
                config[key] = val == 1
                continue

        # 修复 4: number 类型存了非数字，改成默认值
        if param_type == "number":
            if isinstance(val, bool):
                config[key] = meta["default"]
                continue
            if not isinstance(val, (int, float, str)):
                config[key] = meta["default"]
                continue
            if isinstance(val, str):
                try:
                    float(val)
                except ValueError:
                    config[key] = meta["default"]
                    continue

    return config


def load_config() -> Dict[str, Any]:
    """从文件加载已保存的配置（含自动备份损坏文件）"""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                content = f.read()
            if not content or not content.strip():
                raise ValueError("配置文件为空")
            saved = json.loads(content)
            if not isinstance(saved, dict):
                raise ValueError("配置文件格式错误：不是 JSON 对象")
            # 合并默认值，确保新增参数也有值
            defaults = get_default_config()
            defaults.update(saved)
            # 执行类型检查修复
            defaults = _sanitize_config(defaults)
            return defaults
        except Exception as e:
            print(f"[server] ⚠️ 加载配置失败: {e}")
            # 备份损坏的配置文件
            try:
                backup_file = config_file.with_suffix(".json.bak")
                import shutil
                shutil.copy2(str(config_file), str(backup_file))
                print(f"[server] 已备份损坏的配置文件到: {backup_file}")
            except Exception as be:
                print(f"[server] 备份配置文件失败: {be}")
    return get_default_config()


def save_config(config: Dict[str, Any]) -> bool:
    """保存配置到文件"""
    try:
        # 先修复类型不匹配问题再保存
        config = _sanitize_config(config)
        config_dir = get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(get_config_file(), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[server] 保存配置失败: {e}")
        return False


@router.post("/save-as-service")
async def save_as_service():
    """根据当前配置生成 /etc/systemd/system/llama-server.service"""
    try:
        from config import PROJECT_DIR, DATA_DIR, LINKS_DIR

        config = load_config()

        host = config.get("host", "127.0.0.1")
        port = config.get("port", "8080")
        models_max = config.get("models_max", "10")

        models_dir = str(LINKS_DIR) if LINKS_DIR.exists() else str(DATA_DIR)
        models_ini = get_models_ini_path()

        # 查找 llama-server 二进位文件
        server_path = find_llama_server()
        if not server_path:
            return {"success": False, "message": "未找到 llama-server 可执行文件，请先编译 llama.cpp"}

        # 推断运行用户（优先用当前 web 服务的用户，但用 SUDO_USER 替換）
        # 因为 sudo 模式下需要知道原始用户
        import os as os_module
        import pwd
        run_user = "chenbin"
        try:
            sudo_user = os_module.environ.get("SUDO_USER", "")
            if sudo_user and sudo_user != "root":
                run_user = sudo_user
            else:
                # 用 pwd 查询当前有效用户
                run_user = pwd.getpwuid(os_module.getuid()).pw_name
        except:
            pass

        # 推断 WorkingDirectory（llama-server 二进位的上層目錄）
        # 例如 /data/llamapanel/llama.cpp/build/bin/llama-server → /data/llamapanel/llama.cpp
        from pathlib import Path as Pathlib
        sp = Pathlib(server_path).resolve()
        llama_dir = str(sp.parent.parent)  # bin → llama.cpp

        # 生成 service 内容
        service_content = f"""[Unit]
Description=llama.cpp server with GPU and MTP
After=network.target

[Service]
Type=simple
User={run_user}
Group=video
SupplementaryGroups=render
WorkingDirectory={llama_dir}

Environment="CUDA_VISIBLE_DEVICES=0"
Environment="OMP_NUM_THREADS=8"
Environment="LLAMAPANEL_DATA_DIR={DATA_DIR}"

ExecStart={server_path} --models-dir {models_dir} --models-max {models_max} --models-preset {models_ini} --host {host} --port {port} --webui-mcp-proxy

Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/llama-server.log
StandardError=append:/var/log/llama-server-error.log

[Install]
WantedBy=multi-user.target
"""

        # 写入 /etc/systemd/system/llama-server.service
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".service") as tmp:
            tmp.write(service_content)
            tmp_path = tmp.name

        # 用 sudo 复制到 /etc/systemd/system/
        result = subprocess.run(
            ["sudo", "-n", "cp", tmp_path, "/etc/systemd/system/llama-server.service"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            # 如果 sudo -n 失敗（無 NOPASSWD），返回錯誤
            return {
                "success": False,
                "message": f"無法寫入 /etc/systemd/system/llama-server.service（需要 sudo 權限）：{result.stderr}",
                "service_content": service_content,
            }

        # 設置權限
        subprocess.run(["sudo", "-n", "chmod", "644", "/etc/systemd/system/llama-server.service"])

        # daemon-reload
        subprocess.run(["sudo", "-n", "systemctl", "daemon-reload"], capture_output=True, text=True)

        os.unlink(tmp_path)

        return {
            "success": True,
            "message": f"✅ llama-server.service 已生成\n\n{service_content}",
            "service_content": service_content,
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "message": f"生成 service 失敗: {e}\n{traceback.format_exc()}",
        }


@router.post("/start")
async def start_server_api():
    """通过 systemctl 启动 llama-server"""
    try:
        # 检查 service 是否存在
        check = subprocess.run(
            ["systemctl", "cat", "llama-server.service"],
            capture_output=True, text=True, timeout=5
        )
        if check.returncode != 0:
            return {
                "success": False,
                "message": "llama-server.service 不存在。请先在「参数配置」页面点击「保存為 systemd 服務」按鈕。",
            }

        # 检查是否已在运行
        status = subprocess.run(
            ["systemctl", "is-active", "llama-server.service"],
            capture_output=True, text=True, timeout=5
        )
        if status.stdout.strip() == "active":
            return {"success": False, "message": "服务器已在运行中"}

        # 启动
        result = subprocess.run(
            ["sudo", "-n", "systemctl", "start", "llama-server.service"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"success": True, "message": "✅ 启动成功"}
        else:
            return {"success": False, "message": f"啟動失敗: {result.stderr}"}
    except Exception as e:
        return {"success": False, "message": f"啟動失敗: {e}"}


@router.post("/stop")
async def stop_server_api():
    """通过 systemctl 停止 llama-server"""
    try:
        result = subprocess.run(
            ["sudo", "-n", "systemctl", "stop", "llama-server.service"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"success": True, "message": "✅ 停止成功"}
        else:
            return {"success": False, "message": f"停止失敗: {result.stderr}"}
    except Exception as e:
        return {"success": False, "message": f"停止失敗: {e}"}


@router.get("/status")
async def get_server_status_api():
    """通过 systemctl 獲取 llama-server 狀態"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "llama-server.service"],
            capture_output=True, text=True, timeout=5
        )
        is_active = result.stdout.strip() == "active"

        # 獲取 PID
        pid_result = subprocess.run(
            ["systemctl", "show", "llama-server.service", "--property=MainPID"],
            capture_output=True, text=True, timeout=5
        )
        pid = ""
        if pid_result.returncode == 0:
            for line in pid_result.stdout.split("\n"):
                if line.startswith("MainPID="):
                    pid = line.split("=")[1].strip()
                    if pid == "0":
                        pid = ""
                    break

        # 獲取 uptime
        elapsed = ""
        active_result = subprocess.run(
            ["systemctl", "show", "llama-server.service", "--property=ActiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5
        )
        if active_result.returncode == 0:
            import time
            for line in active_result.stdout.split("\n"):
                if line.startswith("ActiveEnterTimestamp="):
                    ts_str = line.split("=")[1].strip()
                    if ts_str:
                        try:
                            from datetime import datetime
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            delta = datetime.now(ts.tzinfo) - ts
                            secs = int(delta.total_seconds())
                            if secs < 60:
                                elapsed = "刚刚"
                            elif secs < 3600:
                                elapsed = f"{secs // 60} 分钟"
                            else:
                                elapsed = f"{secs // 3600} 小时 {(secs % 3600) // 60} 分钟"
                        except:
                            pass
                    break

        server_path = find_llama_server() or "未找到 llama-server，请先编译"

        return {
            "success": True,
            "running": is_active,
            "pid": pid,
            "elapsed": elapsed,
            "server_path": server_path,
        }
    except Exception as e:
        return {"success": False, "running": False, "message": str(e)}


def _check_flag_supported(server_path: str, flag: str) -> bool:
    """检查 llama-server 是否支持某个命令行参数"""
    try:
        result = subprocess.run(
            [server_path, "--help"],
            capture_output=True, text=True, timeout=10
        )
        help_text = result.stdout + result.stderr
        # 在帮助信息中查找该参数
        # 参数可能以 "--mcp" 或 "-mcp" 的形式出现
        flag_clean = flag.lstrip("-")
        return flag_clean in help_text or flag in help_text
    except Exception as e:
        print(f"[server] ⚠️ 检查参数 {flag} 支持情况时出错: {e}")
        # 出错时保守返回 True（假设支持，让 llama-server 自身去报错）
        return True


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
                flag = meta["flag"]
                # 对 --webui-mcp-proxy 参数做可用性检测（防止旧版不支持导致启动失败）
                if key == "mcp" and not _check_flag_supported(server_path, flag):
                    print(f"[server] ⚠️ 当前 llama-server 不支持 {flag} 参数，已跳过 MCP 启用")
                    print(f"[server] 💡 如需使用 MCP 功能，请升级 llama.cpp 到最新版本并重新编译")
                    continue
                cmd.append(flag)
            continue

        # select / 数字 / 文本值：添加参数名和值
        cmd.append(meta["flag"])
        cmd.append(str(value))

    return cmd


def generate_default_models_ini() -> str:
    """生成默认的 models.ini 内容（空模板，不含示例模型）"""
    return ""


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

@router.get("/params-page", response_class=HTMLResponse)
async def params_page():
    """参数配置页面 - 仅参数配置表单和命令预览"""
    return HTMLResponse(content=PARAMS_HTML)


@router.get("/settings-page", response_class=HTMLResponse)
async def server_settings_page():
    """服务器设置页面 - 服务器控制、服务器设置参数和日志"""
    return HTMLResponse(content=SERVER_SETTINGS_HTML)


@router.get("/params-meta")
async def get_params_meta():
    """获取所有参数元数据（前端用于动态渲染表单）"""
    return {
        "success": True,
        "params": SERVER_PARAMS_META,
        "sections": SERVER_PARAMS_SECTIONS,
    }


# ==================== models.ini 多模型配置管理 ====================

@router.get("/models-ini")
async def get_models_ini():
    """读取 models.ini 文件内容"""
    models_ini_path = get_models_ini_path()
    try:
        if models_ini_path.exists():
            with open(models_ini_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content}
        else:
            return {"success": True, "content": ""}
    except Exception as e:
        print(f"[server] 读取 models.ini 失败：{e}")
        return {"success": False, "message": f"读取失败：{e}", "content": ""}


@router.post("/models-ini")
async def save_models_ini(payload: dict = Body(...)):
    """保存 models.ini 文件内容"""
    models_ini_path = get_models_ini_path()
    content = payload.get("content", "")
    try:
        with open(models_ini_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": "models.ini 已保存"}
    except Exception as e:
        print(f"[server] 保存 models.ini 失败：{e}")
        return {"success": False, "message": f"保存失败：{e}"}


@router.get("/model-params/{model_name}")
async def get_model_params(model_name: str):
    """获取指定模型的参数配置"""
    models_ini_path = get_models_ini_path()
    try:
        if not models_ini_path.exists():
            return {"success": True, "params": {}}
        
        with open(models_ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析 INI 内容
        params = {}
        current_section = None
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                continue
            if current_section == model_name and "=" in line:
                key, value = line.split("=", 1)
                params[key.strip()] = value.strip()
        
        return {"success": True, "params": params}
    except Exception as e:
        print(f"[server] 读取模型参数失败：{e}")
        return {"success": False, "message": f"读取失败：{e}", "params": {}}


@router.post("/model-params/{model_name}")
async def save_model_params(model_name: str, payload: dict = Body(...)):
    """保存指定模型的参数配置到 models.ini"""
    models_ini_path = get_models_ini_path()
    params = payload.get("params", {})
    
    try:
        # 读取现有内容
        existing_content = ""
        if models_ini_path.exists():
            with open(models_ini_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        
        # 解析现有内容
        sections = {}
        current_section = None
        section_lines = []
        
        for line in existing_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if current_section:
                    sections[current_section] = section_lines
                current_section = stripped[1:-1].strip()
                section_lines = []
            elif current_section:
                section_lines.append(line)
        
        if current_section:
            sections[current_section] = section_lines
        
        # 更新或添加当前模型的 section
        new_section_lines = [f"[{model_name}]"]
        for key, value in params.items():
            if value is not None and str(value).strip():
                new_section_lines.append(f"{key} = {value}")
        sections[model_name] = new_section_lines
        
        # 重新生成内容
        new_content = ""
        for section_name, lines in sections.items():
            if new_content:
                new_content += "\n"
            new_content += "\n".join(lines) + "\n"
        
        with open(models_ini_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return {"success": True, "message": f"模型 {model_name} 参数已保存"}
    except Exception as e:
        print(f"[server] 保存模型参数失败：{e}")
        return {"success": False, "message": f"保存失败：{e}"}


@router.delete("/model/{model_name}")
async def delete_model(model_name: str):
    """删除指定模型的参数配置"""
    models_ini_path = get_models_ini_path()
    try:
        if not models_ini_path.exists():
            return {"success": True, "message": "配置文件不存在"}
        
        with open(models_ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析并删除指定 section
        lines = content.split("\n")
        new_lines = []
        in_section = False
        section_to_delete = model_name
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped[1:-1].strip()
                if current_section == section_to_delete:
                    in_section = True
                    continue
                else:
                    in_section = False
            if not in_section:
                new_lines.append(line)
        
        new_content = "\n".join(new_lines)
        
        with open(models_ini_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return {"success": True, "message": f"模型 {model_name} 配置已删除"}
    except Exception as e:
        print(f"[server] 删除模型配置失败：{e}")
        return {"success": False, "message": f"删除失败：{e}"}


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


@router.delete("/config")
async def reset_config():
    """删除已保存的配置文件，重置为默认配置"""
    config_file = get_config_file()
    backup_file = config_file.with_suffix(".json.bak")
    deleted = []
    try:
        if config_file.exists():
            config_file.unlink()
            deleted.append(str(config_file))
        if backup_file.exists():
            backup_file.unlink()
            deleted.append(str(backup_file))
        if deleted:
            return {"success": True, "message": f"已删除 {len(deleted)} 个配置文件，配置已重置为默认值"}
        else:
            return {"success": True, "message": "配置文件不存在，已是默认配置"}
    except Exception as e:
        print(f"[server] 重置配置失败: {e}")
        return {"success": False, "message": f"重置配置失败: {e}"}


@router.get("/config-check")
async def check_config():
    """检查配置文件状态，帮助诊断配置问题"""
    config_file = get_config_file()
    backup_file = config_file.with_suffix(".json.bak")
    result = {
        "config_exists": config_file.exists(),
        "backup_exists": backup_file.exists(),
        "config_size": 0,
        "backup_size": 0,
        "config_valid": False,
        "backup_valid": False,
    }
    try:
        if config_file.exists():
            result["config_size"] = config_file.stat().st_size
            with open(config_file, "r", encoding="utf-8") as f:
                json.load(f)
            result["config_valid"] = True
    except Exception as e:
        result["config_error"] = str(e)
    try:
        if backup_file.exists():
            result["backup_size"] = backup_file.stat().st_size
            with open(backup_file, "r", encoding="utf-8") as f:
                json.load(f)
            result["backup_valid"] = True
    except Exception as e:
        result["backup_error"] = str(e)
    return {"success": True, **result}


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


# ==================== INI 多模型配置管理 ====================

@router.get("/models-config")
async def get_models_config():
    """读取 models.ini 多模型配置内容"""
    ini_path = get_models_ini_path()
    if not ini_path.exists():
        # 首次使用，创建默认配置
        content = generate_default_models_ini()
        try:
            with open(ini_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return {"success": False, "content": "", "message": f"创建默认配置失败: {e}"}
        return {"success": True, "content": content}

    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "content": "", "message": f"读取配置失败: {e}"}


@router.post("/models-config")
async def save_models_config(data: dict = Body(...)):
    """保存 models.ini 多模型配置"""
    ini_path = get_models_ini_path()
    content = data.get("content", "")
    if not content:
        return {"success": False, "message": "配置内容为空"}
    try:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": "✅ 模型配置已保存到 models.ini"}
    except Exception as e:
        return {"success": False, "message": f"保存失败: {e}"}


# ==================== models.ini 模型参数管理 ====================

@router.get("/models-ini")
async def get_models_ini():
    """读取 models.ini 文件内容（供前端预览/编辑）"""
    ini_path = get_models_ini_path()
    if not ini_path.exists():
        return {"success": True, "content": "", "message": "models.ini 尚未生成"}
    try:
        with open(ini_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "content": "", "message": f"读取失败：{e}"}


@router.post("/models-ini")
async def save_models_ini(data: dict = Body(...)):
    """保存 models.ini 文件内容（完整文本覆盖）"""
    ini_path = get_models_ini_path()
    content = data.get("content", "")
    if not content:
        return {"success": False, "message": "配置内容为空"}
    try:
        ini_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "message": "✅ models.ini 已保存"}
    except Exception as e:
        return {"success": False, "message": f"保存失败：{e}"}


@router.get("/models-list")
async def get_models_list():
    """获取 models.ini 中的所有模型名称列表"""
    ini_path = get_models_ini_path()
    if not ini_path.exists():
        return {"success": True, "models": []}
    
    try:
        import configparser
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding="utf-8")
        
        models = []
        for section in parser.sections():
            name = parser.get(section, "name", fallback=section)
            models.append({"section": section, "name": name})
        
        return {"success": True, "models": models}
    except Exception as e:
        print(f"[server] 读取模型列表失败：{e}")
        return {"success": False, "models": [], "message": f"读取失败：{e}"}


@router.get("/model-params/{model_name}")
async def get_model_params(model_name: str):
    """获取指定模型的参数（按分区组织，返回各字段的值）"""
    ini_path = get_models_ini_path()
    params = {}
    for key, meta in SERVER_PARAMS_META.items():
        params[key] = meta["default"]
    
    if not ini_path.exists():
        return {"success": True, "params": params}
    
    try:
        import configparser
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding="utf-8")
        
        if not parser.has_section(model_name):
            return {"success": True, "params": params}
        
        for key, meta in SERVER_PARAMS_META.items():
            if parser.has_option(model_name, key):
                raw_val = parser.get(model_name, key)
                if meta["type"] == "checkbox":
                    params[key] = raw_val.lower() in ("true", "1", "yes", "on")
                elif meta["type"] == "number":
                    try:
                        if "." in raw_val:
                            params[key] = float(raw_val)
                        else:
                            params[key] = int(raw_val)
                    except (ValueError, TypeError):
                        params[key] = meta["default"]
                else:
                    params[key] = raw_val
        return {"success": True, "params": params}
    except Exception as e:
        print(f"[server] 读取模型参数失败：{e}")
        return {"success": True, "params": params}


@router.post("/model-params/{model_name}")
async def save_model_params(model_name: str, data: dict = Body(...)):
    """保存指定模型的参数到 models.ini"""
    ini_path = get_models_ini_path()
    submitted = data.get("params", {})
    if not submitted:
        return {"success": False, "message": "参数为空"}
    
    try:
        import configparser
        parser = configparser.ConfigParser()
        
        if ini_path.exists():
            parser.read(ini_path, encoding="utf-8")
        
        if model_name not in parser:
            parser.add_section(model_name)
        
        for key, value in submitted.items():
            if key in SERVER_PARAMS_META:
                meta = SERVER_PARAMS_META[key]
                if meta["type"] == "checkbox":
                    parser.set(model_name, key, "true" if value else "false")
                else:
                    parser.set(model_name, key, str(value))
        
        ini_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ini_path, "w", encoding="utf-8") as f:
            parser.write(f)
        
        return {"success": True, "message": f"✅ 模型「{model_name}」参数已保存"}
    except Exception as e:
        print(f"[server] 保存模型参数失败：{e}")
        return {"success": False, "message": f"保存失败：{e}"}


@router.delete("/model-params/{model_name}")
async def delete_model_params(model_name: str):
    """删除指定模型的配置"""
    ini_path = get_models_ini_path()
    if not ini_path.exists():
        return {"success": False, "message": "models.ini 不存在"}
    
    try:
        import configparser
        parser = configparser.ConfigParser()
        parser.read(ini_path, encoding="utf-8")
        
        if not parser.has_section(model_name):
            return {"success": False, "message": f"模型「{model_name}」不存在"}
        
        parser.remove_section(model_name)
        
        with open(ini_path, "w", encoding="utf-8") as f:
            parser.write(f)
        
        return {"success": True, "message": f"🗑️ 已删除模型「{model_name}」的配置"}
    except Exception as e:
        print(f"[server] 删除模型配置失败：{e}")
        return {"success": False, "message": f"删除失败：{e}"}


@router.get("/start-command")
async def get_start_command():
    """生成带 --models-preset 的完整 llama-server 启动命令（多模型模式）"""
    server_path = find_llama_server()
    if not server_path:
        return {"success": False, "command": "", "message": "未找到 llama-server 可执行文件"}

    # 检查 models.ini 是否存在且有内容
    models_ini = get_models_ini_path()
    if not models_ini.exists():
        return {"success": False, "command": "", "message": "请先在「参数配置」页面添加模型并保存配置"}

    import configparser
    parser = configparser.ConfigParser()
    try:
        parser.read(models_ini, encoding="utf-8")
    except Exception:
        return {"success": False, "command": "", "message": "models.ini 格式错误，请先在参数配置页面检查配置"}
    if len(parser.sections()) == 0:
        return {"success": False, "command": "", "message": "models.ini 中没有配置任何模型，请先在参数配置页面添加模型"}

    # 读取 JSON 配置（服务器级别参数）
    json_config = load_config()

    # 构建命令
    cmd_parts = [server_path]

    # --- models-dir: 使用 LINKS_DIR (模型软链接目录) ---
    from config import LINKS_DIR, MODELS_DIR
    models_dir = str(LINKS_DIR) if LINKS_DIR.exists() else str(MODELS_DIR)
    cmd_parts.extend(["--models-dir", models_dir])

    # --- models-max: 从 JSON 配置或默认 10 ---
    models_max = json_config.get("models_max", "10")
    cmd_parts.extend(["--models-max", str(models_max)])

    # --- models-preset: 指向 models.ini ---
    cmd_parts.extend(["--models-preset", str(models_ini)])

    # --- host ---
    host = json_config.get("host", "127.0.0.1")
    cmd_parts.extend(["--host", host])

    # --- port ---
    port = json_config.get("port", "8080")
    cmd_parts.extend(["--port", str(port)])

    # --- parallel (-np) ---
    parallel = json_config.get("parallel", "1")
    cmd_parts.extend(["-np", str(parallel)])

    # --- cont-batching (-cb) ---
    if json_config.get("cont_batching", True) == True or json_config.get("cont_batching") == "true":
        cmd_parts.append("-cb")

    # --- webui-mcp-proxy ---
    if json_config.get("mcp", False) == True or json_config.get("mcp") == "true":
        if _check_flag_supported(server_path, "--webui-mcp-proxy"):
            cmd_parts.append("--webui-mcp-proxy")
        else:
            print("[server] ⚠️ 当前 llama-server 不支持 --webui-mcp-proxy 参数，已跳过")

    # --- timeout ---
    timeout = json_config.get("timeout", "600")
    if timeout:
        cmd_parts.extend(["--timeout", str(timeout)])

    # 格式化为多行命令（便于阅读）
    cmd_str = " \\\n  ".join(cmd_parts)
    cmd_single = " ".join(cmd_parts)

    return {
        "success": True,
        "command": cmd_str,
        "command_single": cmd_single,
        "cmd_list": cmd_parts,
        "models_ini_path": str(models_ini),
        "models_count": len(parser.sections()),
    }


@router.get("/params/add-model-page")
async def get_add_model_page():
    """添加模型弹窗页面（独立 HTML 页面）"""
    return HTMLResponse(content=ADD_MODEL_POPUP_HTML)


@router.post("/params/add-model")
async def add_model_via_popup(request: Request):
    """弹窗保存新模型到 models.ini"""
    try:
        data = await request.json()
        section_name = data.get("_section", "").strip()
        model_name = data.get("name", "").strip()
        params = data.get("params", {})
        
        if not model_name:
            return {"success": False, "message": "请输入模型名称"}
        if not section_name:
            import re as _re
            section_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", model_name).lower()
        
        models_ini = get_models_ini_path()
        config = configparser.ConfigParser()
        if models_ini.exists():
            config.read(models_ini, encoding="utf-8")
        
        if config.has_section(section_name):
            return {"success": False, "message": f"Section 名称已存在: {section_name}"}
        
        config.add_section(section_name)
        config.set(section_name, "name", model_name)
        
        # 寫入用戶設定的 42 個參數
        for key, val in params.items():
            if val is None or val == "":
                continue
            if isinstance(val, bool):
                config.set(section_name, key, "true" if val else "false")
            else:
                config.set(section_name, key, str(val))
        
        # 確保目錄存在
        models_ini.parent.mkdir(parents=True, exist_ok=True)
        with open(models_ini, "w", encoding="utf-8") as f:
            config.write(f)
        
        return {"success": True, "message": f"模型 {model_name} 已添加", "_section": section_name}
    except Exception as e:
        import traceback
        return {"success": False, "message": f"保存失败: {e}\n{traceback.format_exc()}"}
