"""
私有模块（文件名以 _ 开头）—— 不被 EdgeOne 映射为公开路由
用于配置 LLM 模型。

被 ./index.py 通过 `from ._model import llm_model` 导入。

通过环境变量 AI_GATEWAY_API_KEY / AI_GATEWAY_BASE_URL / LLM_MODEL 配置模型接入。
当前使用腾讯混元 API（tokenhub.tencentmaas.com）。
"""

import os
from dotenv import load_dotenv

load_dotenv()

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel


# LLM 模型接入
llm_client = AsyncOpenAI(
    api_key=os.getenv("AI_GATEWAY_API_KEY"),
    base_url=os.getenv("AI_GATEWAY_BASE_URL"),
)

llm_model = OpenAIChatCompletionsModel(
    model=os.getenv("AI_GATEWAY_MODEL", "@Pages/glm-5"),
    openai_client=llm_client,
)
