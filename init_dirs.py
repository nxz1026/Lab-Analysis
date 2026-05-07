#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_dirs.py - 初始化项目目录结构

根据 WIKI_ROOT 环境变量创建必要的目录结构
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取工作区根目录
WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", Path.cwd()))

def create_directories():
    """创建必要的目录结构"""
    print(f"工作区根目录: {WIKI_ROOT}")
    print("=" * 60)
    
    # 定义需要创建的目录
    dirs_to_create = [
        WIKI_ROOT / "raw" / "Origin_data",
        WIKI_ROOT / "data",
    ]
    
    # 创建目录
    for dir_path in dirs_to_create:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✓ 已创建: {dir_path}")
        except Exception as e:
            print(f"✗ 创建失败 {dir_path}: {e}")
    
    print("=" * 60)
    print("目录结构初始化完成！")
    print(f"\n完整目录结构:")
    print(f"{WIKI_ROOT}/")
    print(f"├── raw/")
    print(f"│   ├── Origin_data/          # 放置原始检验报告图片 (lab_*.jpg)")
    print(f"│   └── patient_{{ID}}/       # 各患者数据（自动生成）")
    print(f"│       ├── papers/           # 检验报告")
    print(f"│       └── imaging/          # 医学影像")
    print(f"└── data/                     # 分析输出（自动生成）")
    print(f"    └── {{ID}}/{{TIMESTAMP}}/")

if __name__ == "__main__":
    create_directories()
