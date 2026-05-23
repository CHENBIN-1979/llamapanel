#!/usr/bin/env python3
"""检查 git commit 中包含的文件列表"""
import zlib, os

def read_obj(sha):
    p = f"D:\\llamapanel\\.git\\objects\\{sha[:2]}\\{sha[2:]}"
    with open(p, 'rb') as f:
        return zlib.decompress(f.read())

commits = [
    ("5577271", "55772714d84107a27f9a64e915fa11d2620b7c85"),  # system.py 动态读取
    ("e5bbd32", "e5bbd3231e5808601a9e97d10b145747e3572457"),  # 系统信息页面移除 llama.cpp 状态栏
]

for label, sha in commits:
    data = read_obj(sha).decode('utf-8', errors='replace')
    print(f"\n=== {label} ({sha[:7]}) ===")
    # 提取 tree sha
    for line in data.split('\n'):
        if line.startswith('tree '):
            tree_sha = line.split()[1]
            print(f"Tree: {tree_sha}")
            # 读取 tree 对象
            tree_data = read_obj(tree_sha)
            # tree 格式: "mode name\0sha" 或 "mode name\0" + 20 bytes sha
            # 更简单的解析: 查找文件名
            text = tree_data.decode('utf-8', errors='replace')
            for f_line in text.split('\n'):
                if f_line.strip():
                    print(f"  File: {f_line}")
            break
