#!/usr/bin/env python3
"""
从 catsapi 后端的两份模型定义生成精简版 capabilities.json,供 skill 的 references 使用。
当前 skill 会按 SUPPORTED_IMAGE_MODELS / SUPPORTED_VIDEO_MODELS 过滤为支持子集。

用法:
    python3 build_capabilities.py \
        --image-models /path/to/backend/app/image_models.json \
        --video-models /path/to/backend/app/abacus_video_models.json \
        --output ../data/capabilities.json

也可以直接从运行中的后端拉取:
    python3 build_capabilities.py --from-api https://catsapi.com --output ../data/capabilities.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import urllib.parse
import urllib.request

from model_catalog import DISPLAY_NAMES, SUPPORTED_MODELS, client_limits

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
SUPPORTED_IMAGE_MODELS = SUPPORTED_MODELS["image"]
SUPPORTED_VIDEO_MODELS = SUPPORTED_MODELS["video"]
PROMPT_LIMIT_KEYS = (
    "max_chars", "maxChars", "maxPromptChars", "max_prompt_chars", "promptMaxChars",
    "max_input_tokens", "maxInputTokens", "max_input_token", "maxInputToken",
)


def _extract_param_schema(schema: dict) -> dict:
    """把模型参数 schema 化简为"名字→options / default"。"""
    slim: dict[str, dict] = {}
    for key, meta in schema.items():
        if key == "_meta" or key in PROMPT_LIMIT_KEYS or not isinstance(meta, dict):
            continue
        opts = meta.get("options", {})
        if isinstance(opts, dict):
            values = opts.get("keys") or opts.get("values") or []
        elif isinstance(opts, list):
            values = opts
        else:
            values = []
        item: dict = {
            "valueType": meta.get("valueType", "string"),
            "type": meta.get("type", "text"),
            "optional": bool(meta.get("optional", True)),
        }
        if meta.get("default") is not None:
            item["default"] = meta.get("default")
        if values:
            item["options"] = values
        if meta.get("maxFiles"):
            item["maxFiles"] = meta["maxFiles"]
        for limit in ("min", "max", "step"):
            if limit in meta:
                item[limit] = meta[limit]
        slim[key] = item
    return slim


def _extract_limits(schema: dict) -> dict:
    metadata = schema.get("_meta", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        key: schema.get(key, metadata.get(key))
        for key in PROMPT_LIMIT_KEYS
        if schema.get(key, metadata.get(key)) is not None
    }


def _build_from_files(image_path: pathlib.Path, video_path: pathlib.Path) -> dict:
    with image_path.open("r", encoding="utf-8") as f:
        img = json.load(f)
    with video_path.open("r", encoding="utf-8") as f:
        vid = json.load(f)

    image_settings = img.get("result", {}).get("settings", {})
    video_settings = vid.get("result", {}).get("settings", {})

    return {
        "source": "local-files",
        "image_models": {
            k: {"display_name": DISPLAY_NAMES[k], "params": _extract_param_schema(v),
                "limits": _extract_limits(v), "client_limits": client_limits(k, v)}
            for k, v in image_settings.items()
            if k in SUPPORTED_IMAGE_MODELS
        },
        "video_models": {
            k: {"display_name": DISPLAY_NAMES[k], "params": _extract_param_schema(v),
                "limits": _extract_limits(v), "client_limits": client_limits(k, v)}
            for k, v in video_settings.items()
            if k in SUPPORTED_VIDEO_MODELS
        },
    }


def _build_from_api(base: str) -> dict:
    def _fetch(task_type: str) -> list[dict]:
        url = f"{base.rstrip('/')}/api/models?type={urllib.parse.quote(task_type)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("models", [])

    img = _fetch("image")
    vid = _fetch("video")
    return {
        "source": f"api:{base}",
        "image_models": {
            m["model_key"]: {
                "display_name": m.get("display_name", ""),
                "base_coin_cost": m.get("base_coin_cost"),
                "resolution_costs": m.get("resolution_costs", {}),
                "supports_image": m.get("supports_image", False),
                "supported_aspect_ratios": m.get("supported_aspect_ratios", []),
                "params": _extract_param_schema(m.get("params_schema", {})),
                "client_limits": client_limits(m["model_key"], m.get("params_schema", {})),
                "limits": {**_extract_limits(m.get("params_schema", {})),
                           **({"max_chars": m["max_prompt_chars"]} if m.get("max_prompt_chars") else {})},
            }
            for m in img
            if m.get("model_key") in SUPPORTED_IMAGE_MODELS
        },
        "video_models": {
            m["model_key"]: {
                "display_name": m.get("display_name", ""),
                "base_coin_cost": m.get("base_coin_cost"),
                "resolution_costs": m.get("resolution_costs", {}),
                "supported_aspect_ratios": m.get("supported_aspect_ratios", []),
                "params": _extract_param_schema(m.get("params_schema", {})),
                "client_limits": client_limits(m["model_key"], m.get("params_schema", {})),
                "limits": {**_extract_limits(m.get("params_schema", {})),
                           **({"max_chars": m["max_prompt_chars"]} if m.get("max_prompt_chars") else {})},
            }
            for m in vid
            if m.get("model_key") in SUPPORTED_VIDEO_MODELS
        },
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Build capabilities.json for catsapi skill")
    p.add_argument("--image-models", type=pathlib.Path,
                   help="image_models.json 路径 (本地文件模式)")
    p.add_argument("--video-models", type=pathlib.Path,
                   help="abacus_video_models.json 路径 (本地文件模式)")
    p.add_argument("--from-api", metavar="BASE_URL",
                   help="从运行中的后端 /api/models 拉取 (需开放无鉴权)")
    p.add_argument("--output", "-o", type=pathlib.Path, required=True,
                   help="输出路径")
    args = p.parse_args()

    if args.from_api:
        data = _build_from_api(args.from_api)
    else:
        if not (args.image_models and args.video_models):
            p.error("非 --from-api 模式下必须同时提供 --image-models 和 --video-models")
        data = _build_from_files(args.image_models, args.video_models)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] wrote {args.output} "
          f"(image={len(data['image_models'])}, video={len(data['video_models'])})")


if __name__ == "__main__":
    main()
