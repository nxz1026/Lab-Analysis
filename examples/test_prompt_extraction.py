"""测试 prompt 提取功能"""
import os
import sys
from pathlib import Path

# 配置 WORK_ROOT
os.environ.setdefault('WORK_ROOT', str(Path.cwd()))
sys.path.insert(0, str(Path.cwd()))

import dspy

# 配置 LLM
api_key = os.environ.get('DEEPSEEK_API_KEY')
if api_key:
    lm = dspy.LM(model='deepseek/deepseek-chat', api_key=api_key, api_base='https://api.deepseek.com/v1')
    dspy.configure(lm=lm)
    print("[OK] LLM configured")
else:
    print("[WARN] DEEPSEEK_API_KEY not set, demos will be empty")

from lab_analysis.dspy_modules.literature_interpreter import LiteratureInterpreterModule
from lab_analysis.dspy_modules.prompt_inspector import (
    extract_module_prompts,
    save_prompts_to_json,
    save_prompts_to_markdown,
)

# 测试 1: 未编译的模块 (无 demos)
print("\n=== Test 1: Uncompiled Module ===")
module = LiteratureInterpreterModule()
data = extract_module_prompts(module, 'literature_interpreter')
print(f'Module type: {data["module_type"]}')
print(f'Total predictors: {len(data["predictors"])}')
print(f'Total demos: {data["total_demos"]}')
for pred in data['predictors']:
    sig = pred['signature']
    print(f'\nPredictor: {pred["predictor_name"]}')
    print(f'  Type: {pred["predictor_type"]}')
    print(f'  Signature: {sig["signature_name"]}')
    print(f'  Instructions length: {len(sig["instructions"])}')
    print(f'  Input fields: {list(sig["input_fields"].keys())}')
    print(f'  Output fields: {list(sig["output_fields"].keys())}')

# 保存到文件
output_dir = Path('data/test_dspy_prompts')
output_dir.mkdir(parents=True, exist_ok=True)
json_path = save_prompts_to_json('literature_interpreter', data, output_dir)
md_path = save_prompts_to_markdown('literature_interpreter', data, output_dir)
print(f'\nSaved JSON: {json_path}')
print(f'Saved MD: {md_path}')

print("\n[OK] All tests passed!")