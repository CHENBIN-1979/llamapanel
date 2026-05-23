#!/usr/bin/env python3
"""检查 tree 对象中的文件名"""
import zlib

def read_obj(sha):
    p = f"D:\\llamapanel\\.git\\objects\\{sha[:2]}\\{sha[2:]}"
    with open(p, 'rb') as f:
        return zlib.decompress(f.read())

# 读取 commit 72b9b3b6 (新建独立系统信息页面)
data = read_obj("72b9b3b60ae4e1118f413f4349c9b2f2ea607c5d")
print("=== Commit 72b9b3b6 ===")
text = data.decode('utf-8', errors='replace')
print(text[:500])

# 提取 tree sha
for line in text.split('\n'):
    if line.startswith('tree '):
        tree_sha = line.split()[1]
        print(f"\nTree SHA: {tree_sha}")
        tree_data = read_obj(tree_sha)
        print(f"Tree size: {len(tree_data)} bytes")
        # 解析 tree 对象 - 格式: "mode name\0sha" 重复
        # 尝试解包
        pos = 0
        while pos < len(tree_data):
            # 找到第一个空格 (mode 结束)
            space = tree_data.find(b' ', pos)
            if space == -1:
                break
            mode = tree_data[pos:space].decode()
            # 找到 null (name 结束)
            null = tree_data.find(b'\0', space+1)
            if null == -1:
                break
            name = tree_data[space+1:null].decode()
            # SHA is 20 bytes after null
            sha = tree_data[null+1:null+21].hex()
            print(f"  {mode} {name} ({sha})")
            pos = null + 21
        break
