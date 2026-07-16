# SERVER_PARAMS_META 完整結構

**總計: 42 個參數，分為 6 個分類**

---

## 📂 模型与路径 (4 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `model` | 模型文件路径 (GGUF) | `-m` | file_picker | `""` |
| `mmproj` | 多模态投影文件 (mmproj) | `--mmproj` | file_picker | `""` |
| `lora` | LoRA 适配器 | `--lora` | text | `""` |
| `lora_base` | LoRA 基座模型 | `--lora-base` | text | `""` |

## 📂 GPU 与加速 (8 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `n_gpu_layers` | GPU 加速层数 (-ngl) | `-ngl` | number | `"0"` |
| `no_kv_offload` | 禁用 KV 缓存 GPU 加速 | `--no-kv-offload` | checkbox | `False` |
| `cache_type_k` | K 缓存压缩类型 | `--cache-type-k` | select | `"f16"` |
| `cache_type_v` | V 缓存压缩类型 | `--cache-type-v` | select | `"f16"` |
| `no_unload` | 模型常驻 GPU 显存 | `--no-unload` | checkbox | `False` |
| `tensor_split` | 多显卡分工比例 | `-ts` | text | `""` |
| `mlock` | 锁定到物理内存 | `--mlock` | checkbox | `False` |
| `no_mmap` | 禁用内存映射加载 | `--no-mmap` | checkbox | `False` |

## 📂 上下文与内存 (6 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `ctx_size` | 上下文大小 (ctx-size) | `-c` | number | `"4096"` |
| `rope_freq_base` | RoPE 频率基数 | `--rope-freq-base` | number | `""` |
| `rope_freq_scale` | RoPE 频率缩放 | `--rope-freq-scale` | number | `""` |
| `rope_scaling` | RoPE 缩放类型 | `--rope-scaling` | select | `"yarn"` |
| `rope_scale` | RoPE 上下文缩放 | `--rope-scale` | number | `"2.0"` |
| `yarn_orig_ctx` | YaRN 原始上下文大小 | `--yarn-orig-ctx` | number | `"32768"` |

## 📂 采样参数 (7 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `temp` | 温度 (Temperature) | `--temp` | number | `"0.8"` |
| `top_k` | Top-K | `--top-k` | number | `"40"` |
| `top_p` | Top-P (核采样) | `--top-p` | number | `"0.95"` |
| `min_p` | Min-P | `--min-p` | number | `"0.05"` |
| `repeat_penalty` | 重复惩罚 | `--repeat-penalty` | number | `"1.1"` |
| `repeat_last_n` | 重复惩罚窗口 | `--repeat-last-n` | number | `"64"` |
| `presence_penalty` | 存在惩罚 (presence-penalty) | `--presence-penalty` | number | `"0.0"` |

## 📂 服务器设置 (11 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `host` | 监听地址 (Host) | `--host` | text | `"127.0.0.1"` |
| `port` | 监听端口 (Port) | `--port` | number | `"8080"` |
| `timeout` | 模型自动卸载空闲超时 (秒) | `--timeout` | number | `"600"` |
| `parallel` | 并行序列数 | `-np` | number | `"1"` |
| `cont_batching` | 启用持续批处理 | `-cb` | checkbox | `True` |
| `slots` | 最大 slots 数 | `--slots` | number | `""` |
| `slot_save_path` | Slot KV 缓存保存路径 | `--slot-save-path` | text | `""` |
| `embeddings` | 启用嵌入模式 | `--embeddings` | checkbox | `False` |
| `no_webui` | 禁用 WebUI | `--no-webui` | checkbox | `False` |
| `jinja` | 启用 Jinja2 模板 | `--jinja` | checkbox | `True` |
| `mcp` | 启用 WebUI MCP Proxy | `--webui-mcp-proxy` | checkbox | `False` |

## 📂 线程与性能 (6 個參數)

| Key | 標籤 | Flag | 類型 | 預設值 |
|---|---|---|---|---|
| `threads` | 生成线程数 | `-t` | number | `"8"` |
| `threads_batch` | 批处理线程数 | `--threads-batch` | number | `""` |
| `batch_size` | 批处理大小 (batch-size) | `-b` | number | `"2048"` |
| `ubatch_size` | 物理批处理大小 (ubatch-size) | `-ub` | number | `"512"` |
| `flash_attn` | Flash Attention 加速 | `--flash-attn` | select | `"on"` |
| `n_cpu_moe` | MoE 专家 CPU 核心数 | `--n-cpu-moe` | number | `"0"` |

