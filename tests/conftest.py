import os

for key in (
    "ARK_API_KEY",
    "CIELO_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
):
    os.environ[key] = ""
