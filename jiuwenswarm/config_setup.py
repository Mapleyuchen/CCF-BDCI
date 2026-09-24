"""
配置文件生成脚本
用于设置JiuwenSwarm的模型配置
"""
import os
import yaml
from pathlib import Path

# API配置
API_KEY = "sk-8Uzt9TAdf22plTnkY4TCpxJfG1SCB2WDnejdnqZzAvT8u2Pj"
MODEL_NAME = "gemini-3-flash-preview"
API_BASE = "https://new.ch-at.pw/v1"

def setup_config():
    """创建JiuwenSwarm配置文件"""

    # 配置目录
    config_dir = Path.home() / ".jiuwenswarm" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.yaml"

    # 基础配置
    config = {
        "model_name": MODEL_NAME,
        "api_base": API_BASE,
        "api_key": API_KEY,
        "model_provider": "OpenAI",  # 使用OpenAI兼容接口
        "react": {
            "evolution": {
                "skill_evolution": True,  # 启用Skill自演进
                "auto_save": False
            }
        },
        "memory": {
            "external": {
                "provider": "openjiuwen",
                "user_id": "ccf_bdci_user"
            }
        }
    }

    # 保存配置
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"配置文件已创建: {config_file}")
    print(f"模型: {MODEL_NAME}")
    print(f"API Base: {API_BASE}")

    return config_file

if __name__ == "__main__":
    setup_config()
