#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 统一入口（薄 shim，代理到 lab_analysis.pipeline 子包）

用法：
  仓库根目录：python -m lab_analysis
  （运行时强制交互输入身份证号，不再支持 --patient-id 参数）
"""

from lab_analysis.pipeline.run import main

if __name__ == "__main__":
    main()
