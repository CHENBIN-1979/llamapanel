# LlamaPanel

- llama.cpp 图形化管理面板 - 无需命令行
- 这只是为了方便操作llama.cpp并非llama.cpp分支，实际使用的还是llama.cpp

## 功能

- 🚀 一键安装 llama.cpp
- 🔄 自动检测硬件（CPU核心数、GPU）
- 📊 实时编译进度显示
- 📋 彩色日志输出
- 🧹 清理编译产物
- 📥 模型搜索下载（从 HuggingFace）
- 💾 本地模型管理（断点续传）
- ⚙️ 智能使用一半CPU核心编译，不影响Web服务

## 系统要求

- Ubuntu 24.04（推荐）
- 2GB+ 内存
- 2GB+ 磁盘空间
- Python 3.8+

## 一键安装（服务器）

```bash
git clone https://github.com/CHENBIN-1979/llamapanel.git
cd llamapanel
chmod +x install.sh
sudo ./install.sh
sudo systemctl start llamapanel
```

## 本地开发

```bash
# 克隆项目
git clone https://github.com/CHENBIN-1979/llamapanel.git
cd llamapanel

# 创建虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
cd backend
python app.py
# 访问 http://localhost:8000
```

## 系统启动命令

- 启动服务: `sudo systemctl start llamapanel`
- 开机自启: `sudo systemctl enable llamapanel`
- 查看状态: `sudo systemctl status llamapanel`
- 查看日志: `sudo journalctl -u llamapanel -f`

## 访问地址

 http://主机IP:8000

## 版本更新

1. 点击「更新版本」（update_llama_cpp() 只更新代码，不更新 llama-server 二进制文件）
2. 点击「重新编译」（更新代码后需要点击「重新编译」才能生成新的 llama-server）

## 注意事项

- 面板更新功能需要 `llamapanel` 用户有 sudo 权限重启服务（安装脚本已自动配置）
- 模型下载支持断点续传和暂停/继续
- 删除或更新 llama.cpp 目录不会影响已下载的模型
