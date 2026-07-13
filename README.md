# LlamaPanel

- llama.cpp 图形化管理面板 - 无需命令行
- 这只是为了方便操作llama.cpp并非llama.cpp分支，实际使用的还是llama.cpp

## 功能

- 一键安装 llama.cpp
- 自动检测硬件（CPU核心数、GPU）
- 实时编译进度显示
- 彩色日志输出
- 清理编译产物
- 模型搜索下载（从 HuggingFace）
- 本地模型管理（断点续传）
- 智能使用一半CPU核心编译，不影响Web服务
- Web UI 一键更新 LlamaPanel（无需手动 git pull）

## 系统要求

- Ubuntu 24.04（推荐）
- 2GB+ 内存
- 2GB+ 磁盘空间
- Python 3.8+

## 一键安装（服务器）

### 方式 A：用普通用户安装（推荐）

```bash
# 用你的普通用户（如 chenbin）登入
cd ~
git clone https://github.com/CHENBIN-1979/llamapanel.git
cd llamapanel
chmod +x install.sh
sudo ./install.sh
sudo systemctl start llamapanel
```

### 方式 B：用 root 安装

```bash
cd /root
git clone https://github.com/CHENBIN-1979/llamapanel.git
cd llamapanel
chmod +x install.sh
./install.sh
sudo systemctl start llamapanel
```

> install.sh 会自动侦测当前用户，**不需要手动 chown**。

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

- 默认端口: `http://主机IP:8000`
- 如使用 1Panel 等面板，请记得在防火墙放行 8000 端口

## Web UI 更新

**推荐方式：直接在 LlamaPanel 面板内点击「更新 LlamaPanel」按钮**

- 自动 git pull
- 自动修复 .git 权限
- 自动安装 Python 依赖
- 自动重启服务

## 命令行手动更新

```bash
# 1. 進到你的 llamapanel 安裝目錄
cd /your/llamapanel/path

# 2. 如果遇到 dubious ownership 错误，先执行：
sudo git config --global --add safe.directory $(pwd)

# 3. 拉新代码
sudo git pull

# 4. 重启服务才生效
sudo systemctl restart llamapanel
```

## .git 权限问题

如果更新时遇到 `insufficient permission` 错误：

```bash
# 一次性解决（将 .git 设为所有用户可写）
sudo chmod -R 777 /your/llamapanel/.git
```

之后更新按钮就能正常拉取新代码。

## 故障排查

```bash
# 查看服务实际使用的目录
sudo systemctl show llamapanel -p WorkingDirectory

# 查看最近的错误日志
sudo journalctl -u llamapanel --since "5 minutes ago"
```

如果服务 WorkingDirectory 和你 git pull 的目录不一致，需要调整安装路径。

## 版本更新

1. 点击「更新版本」（update_llama_cpp() 只更新代码，不更新 llama-server 二进制文件）
2. 点击「重新编译」（更新代码后需要点击「重新编译」才能生成新的 llama-server）

## 注意事项

- 面板更新功能需要服务运行用户有 sudo 权限（安装脚本已自动配置）
- 模型下载支持断点续传和暂停/继续
- 删除或更新 llama.cpp 目录不会影响已下载的模型
- 数据存储在 `/data/llamapanel/`，与代码完全分离
