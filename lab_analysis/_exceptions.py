"""_exceptions.py — 共享异常元组常量，替代遍布全项目的重复 except 元组"""
# 宽泛的 IO/类型/属性 异常集合，用于非关键路径的降级处理
SAFE_EXCEPTIONS = (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError)
