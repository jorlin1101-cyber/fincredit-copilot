"""Run minimal, low-cost connectivity checks for the three Bailian model chains."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_PACKAGE = PROJECT_ROOT / "packages" / "api"
sys.path.insert(0, str(API_PACKAGE))
load_dotenv(PROJECT_ROOT / ".env")

from src.inference.config import load_config  # noqa: E402

# One opaque white PNG pixel. It is sufficient to verify image input routing.
WHITE_PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAusB9Y9Z1ZkAAAAASUVORK5CYII="
)


def _client(model: dict) -> AsyncOpenAI:
    api_key = model.get("api_key")
    if not api_key or api_key == "not-needed":
        raise RuntimeError("DASHSCOPE_API_KEY is empty in the project .env file")
    return AsyncOpenAI(base_url=model["endpoint"], api_key=api_key, timeout=45.0)


async def check_text(model: dict) -> None:
    response = await _client(model).chat.completions.create(
        model=model["model_name"],
        messages=[{"role": "user", "content": "请调用 status 工具。"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "status",
                    "description": "返回模型连通状态",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "status"}},
        max_tokens=32,
    )
    if not response.choices[0].message.tool_calls:
        raise RuntimeError("Text model responded but did not return the forced tool call")
    print(f"PASS text/tool calling: {model['model_name']}")


async def check_vision(model: dict) -> None:
    response = await _client(model).chat.completions.create(
        model=model["model_name"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "识别图片主色，只回复一个中文颜色。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{WHITE_PIXEL}"},
                    },
                ],
            }
        ],
        max_tokens=16,
    )
    if not response.choices[0].message.content:
        raise RuntimeError("Vision model returned empty content")
    print(f"PASS vision/image input: {model['model_name']}")


async def check_embedding(model: dict) -> None:
    dimensions = int(model["dimensions"])
    response = await _client(model).embeddings.create(
        model=model["model_name"],
        input=["成都住房贷款政策检索连通性测试"],
        dimensions=dimensions,
        encoding_format="float",
    )
    actual = len(response.data[0].embedding)
    if actual != dimensions:
        raise RuntimeError(f"Embedding width mismatch: expected {dimensions}, got {actual}")
    print(f"PASS embedding/{dimensions}d: {model['model_name']}")


async def main() -> None:
    models = load_config()["models"]
    await check_text(models["llm"])
    await check_vision(models["vision"])
    await check_embedding(models["embedding"])


if __name__ == "__main__":
    asyncio.run(main())
