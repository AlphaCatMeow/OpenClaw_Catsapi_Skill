#!/usr/bin/env python3
"""
CatsAPI Client — OpenClaw Skill 的统一命令行客户端

支持的动作:
    --check                 验证 API Key + 查询余额
    --list                  列出可用模型 (--type image|video)
    --info MODEL_KEY        查看单个模型的参数定义
    --cost                  费用预览 (--type / --model / --resolution / --duration / --num)
    --generate              参数校验、费用预览、提交并下载 (可 --dry-run / --no-wait)
    --resume TASK_ID        等待并下载已有任务，不创建新任务
    --status TASK_ID        查询单个任务状态

环境变量:
    CATSAPI_API_KEY         形如 `cats-xxxxxxxx`;未继承环境变量时会尝试读取本地配置
    CATSAPI_BASE            可选,默认 https://catsapi.com

所有输出:
    - 普通信息走 stderr
    - 结构化结果走 stdout (--json 生命周期事件为 NDJSON；兼容 KEY:VALUE)
    - 任务成功时额外打印 `COST:N` 行 (N 为本次消耗的猫币)
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import mimetypes
import os
import pathlib
import re
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from model_catalog import (
    DEFAULT_PROMPT_LIMIT, DISPLAY_NAMES, MODEL_ALIASES, SEEDANCE_MODELS,
    SEEDANCE_REFERENCE_IMAGE_LIMIT, SUPPORTED_MODELS, alias_key, client_limits,
)

DEFAULT_BASE = "https://catsapi.com"
POLL_INTERVAL = 3
POLL_TIMEOUT = 900  # 15 分钟
API_KEY_ENV = "CATSAPI_API_KEY"
# The main site's worker caps combined inputs at 4, despite schema maxFiles=9.
SEEDANCE20_REFERENCE_IMAGE_LIMIT = SEEDANCE_REFERENCE_IMAGE_LIMIT
# 默认 Python urllib 的 UA 会被 catsapi.com 前面的 Cloudflare Bot Fight Mode 拦成 403,
# 伪装成浏览器避免被指纹墙误伤。
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _normalize_model(model_key: str | None, task_type: str) -> str | None:
    if not model_key:
        return None
    normalized = MODEL_ALIASES.get(alias_key(model_key), model_key)
    allowed = SUPPORTED_MODELS.get(task_type, set())
    if normalized not in allowed:
        supported = ", ".join(sorted(allowed))
        _die(f"此 skill 当前不支持模型 `{model_key}`。type={task_type} 仅支持: {supported}")
    return normalized


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _die(msg: str, code: int = 1) -> "None":
    _log(f"[ERROR] {msg}")
    sys.exit(code)


def _base_url() -> str:
    return os.environ.get("CATSAPI_BASE", DEFAULT_BASE).rstrip("/")


def _looks_truncated_key(key: str) -> bool:
    return "..." in key or "…" in key


def _unquote_shell_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        parts = shlex.split(value, comments=True, posix=True)
    except ValueError:
        parts = []
    if parts:
        return parts[0].strip()
    # Drop a trailing inline comment for unquoted values.
    if value[0] not in {"'", '"'} and " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1].strip()
    return value.strip()


def _read_key_assignment(path: pathlib.Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    pattern = re.compile(rf"^\s*(?:export\s+)?{API_KEY_ENV}\s*=\s*(.+?)\s*$")
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            return _unquote_shell_value(match.group(1))
    return ""


def _candidate_key_files() -> list[pathlib.Path]:
    base_dir = pathlib.Path(__file__).resolve().parents[1]
    cwd = pathlib.Path.cwd()
    home = pathlib.Path.home()
    paths = [
        base_dir / ".env",
        cwd / ".env",
        home / ".catsapi.env",
        home / ".zshrc",
        home / ".bashrc",
        home / ".profile",
        home / ".bash_profile",
    ]
    seen: set[pathlib.Path] = set()
    unique: list[pathlib.Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _find_configured_api_key() -> str:
    env_key = os.environ.get(API_KEY_ENV, "").strip()
    if env_key:
        return env_key
    for path in _candidate_key_files():
        key = _read_key_assignment(path).strip()
        if key:
            return key
    return ""


def _api_key() -> str:
    key = _find_configured_api_key()
    if not key:
        _die("未找到有效 CATSAPI_API_KEY。\n"
             "请在 catsapi.com 登录后 → 个人中心 → API Key → 创建,然后配置完整 Key。")
    if _looks_truncated_key(key):
        _die("CATSAPI_API_KEY 配置无效: 看起来像被省略或截断的占位符。"
             "请重新复制完整 Key 后配置。")
    if not key.startswith("cats-"):
        _log("[WARN] API Key 看起来不像 catsapi 的格式 (应以 `cats-` 开头)")
    return key


def _request(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    url = f"{_base_url()}{path}"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    data: bytes | None = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    unknown_submission = "Submission outcome may be unknown. Check the website before submitting again; no automatic retry."
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if method == "POST" and path == "/api/tasks" and e.code >= 500:
            _log(f"[WARN] {unknown_submission}")
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            detail = parsed.get("detail", "Request failed") if isinstance(parsed, dict) else "Request failed"
        except Exception:
            detail = "Non-JSON response; check service availability or access restrictions."
        _die(f"HTTP {e.code} {method} {path} → {detail}", code=2)
    except (urllib.error.URLError, OSError):
        if method == "POST" and path == "/api/tasks":
            _log(f"[WARN] {unknown_submission}")
        _die(f"Network error during {method} {path}; check connectivity and service status.", code=3)

    if not raw.strip():
        return {}
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        return result
    except ValueError:
        if method == "POST" and path == "/api/tasks":
            _log(f"[WARN] {unknown_submission}")
        _die("Invalid API JSON response; no response body was printed.", code=4)
        return {}  # unreachable


def _get(path: str) -> dict:
    return _request("GET", path)


def _post(path: str, body: dict) -> dict:
    return _request("POST", path, body)


# ─────────────────────────── Actions ───────────────────────────


def cmd_check() -> None:
    bal = _get("/api/coins/balance")
    _log(f"[OK] API Key 有效,当前余额 {bal.get('balance', 0)} 猫币")
    print(json.dumps(bal, ensure_ascii=False))


def _capabilities() -> dict:
    path = pathlib.Path(__file__).resolve().parents[1] / "data/capabilities.json"
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, ValueError):
        _die("Cannot read data/capabilities.json; restore or rebuild the skill's capability snapshot.")


def cmd_list(task_type: str, offline: bool = False) -> None:
    if offline:
        models = _capabilities()[f"{task_type}_models"]
        print(json.dumps({"source": "offline-snapshot", "live_availability_checked": False,
                          "models": [{"model_key": key, "display_name": DISPLAY_NAMES[key],
                                      "client_limits": model.get("client_limits", {})}
                                     for key, model in models.items()]}, ensure_ascii=False, indent=2))
        return
    data = _get(f"/api/models?type={urllib.parse.quote(task_type)}")
    allowed = SUPPORTED_MODELS.get(task_type, set())
    models = [m for m in data.get("models", []) if m.get("model_key") in allowed]
    _log(f"[OK] {task_type} 模型共 {len(models)} 个 (skill allowlist)")
    slim = [
        {
            "model_key": m["model_key"],
            "display_name": m["display_name"],
            "base_coin_cost": m["base_coin_cost"],
            "resolution_costs": m.get("resolution_costs", {}),
            "supports_image": m.get("supports_image", False),
            "supported_aspect_ratios": m.get("supported_aspect_ratios", []),
        }
        for m in models
    ]
    print(json.dumps(slim, ensure_ascii=False, indent=2))


def cmd_info(model_key: str, task_type: str, offline: bool = False) -> None:
    model_key = _normalize_model(model_key, task_type) or model_key
    if offline:
        model = _capabilities()[f"{task_type}_models"][model_key]
        print(json.dumps({"source": "offline-snapshot", "model_key": model_key, **model},
                         ensure_ascii=False, indent=2))
        return
    data = _get(f"/api/models?type={urllib.parse.quote(task_type)}")
    for m in data.get("models", []):
        if m["model_key"] == model_key:
            print(json.dumps({**m, "client_limits": client_limits(model_key, m.get("params_schema", {}))},
                             ensure_ascii=False, indent=2))
            return
    _die(f"模型 `{model_key}` 未在 type={task_type} 的启用列表中。用 --list --type {task_type} 查看")


def cmd_cost(args: argparse.Namespace) -> None:
    body = _build_generation_body(args, include_media=False)
    data = _post("/api/tasks/cost-preview", _cost_body(body, args))
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_params(raw_params: list[str]) -> dict:
    out: dict[str, Any] = {}
    for item in raw_params or []:
        if "=" not in item:
            _die(f"--param 格式必须是 key=value,收到: {item!r}")
        k, v = item.split("=", 1)
        key = k.strip()
        if key in out:
            _die(f"Duplicate --param: {key}")
        out[key] = v
    return out


def _encode_image(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        _die(f"文件不存在: {path}")
    mime, _ = mimetypes.guess_type(p.name)
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        _die("Image inputs must be JPG, PNG or WEBP; video/audio files are not supported by this client.")
    if p.stat().st_size > 10 * 1024 * 1024:
        _die("Each input image must be no larger than 10 MB.")
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"name": p.name, "base64": f"data:{mime};base64,{b64}"}


def _download(url: str, out_path: str) -> None:
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
        _die("Unsupported result URL scheme.", code=5)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    created = False
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, out.open("xb") as f:
            created = True
            first = True
            while True:
                chunk = resp.read(65536)
                if first:
                    head = chunk.lstrip().lower()
                    if not chunk or head.startswith((b"<!doctype html", b"<html")):
                        raise ValueError("empty response or HTML challenge")
                    first = False
                if not chunk:
                    break
                f.write(chunk)
    except Exception:
        if created:
            out.unlink(missing_ok=True)
        _die("Download failed; use --resume with the existing task ID. Do not generate again.", code=5)


def _coerce_param(key: str, value: Any, field: dict) -> Any:
    kind = field.get("valueType", "string")
    if kind == "boolean":
        if str(value).lower() not in {"true", "false"}:
            _die(f"{key} must be true or false.")
        value = str(value).lower() == "true"
    elif kind == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            _die(f"{key} must be a finite number.")
        if not math.isfinite(number):
            _die(f"{key} must be a finite number.")
        value = int(number) if number.is_integer() else number
        if ("min" in field and value < field["min"]) or ("max" in field and value > field["max"]):
            _die(f"{key} is outside the supported range.")
    else:
        value = str(value)
    options = field.get("options", [])
    if options and value not in options:
        _die(f"{key} does not support {value!r}; allowed: {', '.join(map(str, options))}")
    return value


def _resolve_params(args: argparse.Namespace, schema: dict) -> dict:
    supplied = _parse_params(args.param)
    for flag, fields in (("resolution", ("resolution", "size", "imageSize")),
                         ("duration", ("duration",)), ("mode", ("mode", "quality"))):
        value = getattr(args, flag, None)
        if value is None:
            continue
        key = next((field for field in fields if field in schema), None)
        if not key:
            _die(f"{args.model} does not accept --{flag}.")
        if key in supplied and str(supplied[key]) != str(value):
            _die(f"Conflicting values for {key}.")
        supplied[key] = value
    if args.rewrite_prompt:
        if "rewritePrompt" in supplied and str(supplied["rewritePrompt"]).lower() != "true":
            _die("Conflicting values for rewritePrompt.")
        supplied["rewritePrompt"] = True
    params = {}
    for key, field in schema.items():
        if key in {"prompt", "numImages"} or field.get("type") in {"file", "file_list", "element_list"}:
            continue
        if "default" in field:
            params[key] = _coerce_param(key, field["default"], field)
    for key, value in supplied.items():
        field = schema.get(key)
        if not field or key in {"prompt", "numImages"}:
            _die(f"Unsupported parameter {key!r}; use --info {args.model} --type {args.type} --offline.")
        if field.get("type") in {"file", "file_list", "element_list"}:
            _die(f"Do not place {key} in --param; use the supported image input flags.")
        params[key] = _coerce_param(key, value, field)
    return params


def _build_generation_body(args: argparse.Namespace, include_media: bool = True) -> dict:
    args.model = _normalize_model(args.model, args.type)
    if args.type == "image" and (args.start_frame or args.end_frame or args.reference_image):
        _die("图片任务请用 --image 传参考图; --start-frame/--end-frame/--reference-image 仅用于视频任务")
    if args.type == "video" and args.image:
        _die("视频任务请用 --start-frame 或 --reference-image 传图片素材,不要用 --image")
    if (args.end_frame or args.reference_image) and args.model not in SEEDANCE_MODELS:
        _die("--end-frame and --reference-image are only supported by Seedance 2.0 / Mini.")
    capability = _capabilities()[f"{args.type}_models"][args.model]
    schema = capability["params"]
    params = _resolve_params(args, schema)
    max_chars = capability.get("limits", {}).get("max_chars", DEFAULT_PROMPT_LIMIT)
    if len((args.prompt or "").strip()) > max_chars:
        _die(f"{args.model} 提示词最多 {max_chars} 字符")
    if args.generate and not (args.prompt or "").strip():
        _die("Generation requires a non-empty --prompt.")
    image_limit = schema.get("imagePrompt", {}).get("maxFiles", 1)
    if len(args.image) > image_limit:
        _die(f"{args.model} 最多支持 {image_limit} 张参考图")
    counts = schema.get("numImages", {}).get("options", ["1"])
    if str(args.num) not in [str(count) for count in counts]:
        _die(f"{args.model} supports --num values: {', '.join(map(str, counts))}")
    if args.model in SEEDANCE_MODELS:
        params["inputMode"] = "reference"
        reference_paths = ([args.start_frame] if args.start_frame else []) + args.reference_image
        reference_paths += [args.end_frame] if args.end_frame else []
        if len(reference_paths) > SEEDANCE20_REFERENCE_IMAGE_LIMIT:
            _die("Seedance 2.0 / Mini accept at most 4 images in total (start + references + end).")
    body: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt or "",
        "task_type": args.type,
        "params": params,
        "num_images": args.num,
        "locale": args.locale,
    }
    encode = _encode_image if include_media else lambda path: {"name": pathlib.Path(path).name}
    if args.image:
        body["images"] = [encode(p) for p in args.image]
    if args.model in SEEDANCE_MODELS:
        if reference_paths:
            body["files"] = {"referenceImages": [encode(p) for p in reference_paths]}
    elif args.start_frame:
        body.setdefault("files", {})["startFrame"] = encode(args.start_frame)
    return body


def _cost_body(body: dict, args: argparse.Namespace) -> dict:
    params = body["params"]
    result = {
        "model": body["model"], "task_type": body["task_type"],
        "num_images": body["num_images"],
        "has_image_input": bool(body.get("images") or body.get("files") or args.has_image_input),
        "rewrite_prompt": params.get("rewritePrompt", False),
    }
    for key, fields in (("resolution", ("resolution", "size", "imageSize")),
                        ("duration", ("duration",)), ("mode", ("mode", "quality"))):
        for field in fields:
            if field in params:
                result[key] = str(params[field])
                break
    return result


def _check_cost(data: dict, max_coins: int) -> None:
    total = data.get("total_cost")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total) or total < 0:
        _die("Invalid cost preview; task was not submitted.")
    if data.get("sufficient") is not True:
        _die("Insufficient balance or incomplete cost preview; task was not submitted.")
    if max_coins and total > max_coins:
        _die(f"Estimated cost {total} exceeds --max-coins {max_coins}; task was not submitted.")


def cmd_generate(args: argparse.Namespace) -> None:
    body = _build_generation_body(args, include_media=not args.dry_run)
    if args.output:
        _available_output(pathlib.Path(args.output))  # Reject directory targets before any paid submission.
    cost_request = _cost_body(body, args)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "source": "offline-snapshot", "request": body,
                          "cost_preview_request": cost_request, "max_coins": args.max_coins,
                          "note": "No network, credentials, media encoding or file writes; live availability and media contents are not checked."},
                         ensure_ascii=False, indent=2))
        return
    cost = _post("/api/tasks/cost-preview", cost_request)
    _check_cost(cost, args.max_coins)
    _log(f"[INFO] Estimated cost: {cost['total_cost']} coins")
    _log(f"[INFO] 提交 {args.type} 任务 model={args.model} ...")
    task = _post("/api/tasks", body)
    task_id = task.get("id")
    if not task_id:
        _die("Submission returned no task ID. Check the website before retrying; outcome may be unknown.")
    task_id = str(task_id)
    if args.json:
        _emit_json({"event": "submitted", "task_id": task_id, "model": args.model,
                    "task_type": args.type, "estimated_cost": cost["total_cost"]})
    else:
        print(f"TASK_ID:{task_id}", flush=True)
    if args.no_wait:
        return
    detail = _wait_for_task(task_id, args.wait_timeout)
    _deliver(detail, args, task_id, args.type)


def _emit_json(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False), flush=True)


def _wait_for_task(task_id: str, timeout: float) -> dict:
    start = time.monotonic()
    while True:
        detail = _get(f"/api/tasks/{urllib.parse.quote(task_id, safe='')}")
        status = detail.get("status", "")
        elapsed = time.monotonic() - start
        _log(f"[POLL] {int(elapsed)}s status={status}")
        if status == "completed":
            return detail
        if status in {"failed", "cancelled", "canceled"}:
            _die(f"Task {task_id} {status}: {detail.get('error_message') or 'see task details'}. No new task was submitted.")
        if elapsed >= timeout:
            _die(f"Wait timed out; task may still be {status}. Continue with --resume {task_id}; do not submit again.", code=6)
        time.sleep(min(POLL_INTERVAL, timeout - elapsed))


def _available_output(path: pathlib.Path) -> pathlib.Path:
    path = path.expanduser().resolve()
    if path.is_dir():
        _die("--output must name a file, not a directory.")
    candidate = path
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{suffix}{path.suffix}")
        suffix += 1
    return candidate


def _deliver(detail: dict, args: argparse.Namespace, task_id: str, task_type: str) -> None:
    cost = detail.get("cost")
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)
    extension = "mp4" if task_type == "video" else "png"
    base = pathlib.Path(args.output) if args.output else pathlib.Path.cwd() / "catsapi-output" / f"{task_type}_{safe_id}.{extension}"
    out_paths: list[str] = []
    if task_type == "video":
        vid = detail.get("result_video") or {}
        url = vid.get("url") or vid.get("videoUrl") or vid.get("video_url")
        if not url:
            _die("Completed task has no downloadable video; do not regenerate automatically.")
        out = str(_available_output(base))
        _download(url, out)
        out_paths.append(out)
    else:
        imgs = detail.get("result_images") or []
        if not imgs:
            _die("图片任务完成但未返回图片")
        for i, item in enumerate(imgs):
            url = item.get("url") if isinstance(item, dict) else item
            if not url:
                _die("Completed task has an incomplete image result; use --resume later, not --generate.")
            target_path = base if len(imgs) == 1 else base.with_name(f"{base.stem}_{i+1}{base.suffix}")
            target = str(_available_output(target_path))
            _download(url, target)
            out_paths.append(target)
    if args.json:
        _emit_json({"event": "completed", "task_id": task_id, "task_type": task_type,
                    "cost": cost, "output_files": out_paths})
    else:
        print(f"COST:{cost if cost is not None else 'unknown'}")
        for path in out_paths:
            print(f"OUTPUT_FILE:{path}", flush=True)
    _log(f"[OK] 完成,共 {len(out_paths)} 个文件,消耗 {cost} 猫币")


def cmd_resume(args: argparse.Namespace) -> None:
    if args.json:
        _emit_json({"event": "resuming", "task_id": args.resume})
    else:
        print(f"TASK_ID:{args.resume}", flush=True)
    detail = _wait_for_task(args.resume, args.wait_timeout)
    task_type = detail.get("task_type")
    if task_type not in {"image", "video"}:
        task_type = "video" if detail.get("result_video") else "image"
    _deliver(detail, args, args.resume, task_type)


def cmd_status(task_id: str) -> None:
    data = _get(f"/api/tasks/{urllib.parse.quote(task_id, safe='')}")
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ─────────────────────────── Argparse ───────────────────────────


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="catsapi.py",
        description="CatsAPI client for OpenClaw Skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="校验 API Key + 查余额")
    g.add_argument("--list", action="store_true", help="列出启用模型")
    g.add_argument("--info", metavar="MODEL_KEY", help="查看单个模型参数")
    g.add_argument("--cost", action="store_true", help="费用预览")
    g.add_argument("--generate", action="store_true", help="提交任务并等待完成")
    g.add_argument("--status", metavar="TASK_ID", help="查询任务状态")
    g.add_argument("--resume", metavar="TASK_ID", help="等待并下载已有任务,不重新提交 / Wait for and download an existing task")

    p.add_argument("--type", choices=["image", "video"], default="image",
                   help="任务类型 (默认 image)")
    p.add_argument("--model", help="模型 key,例如 nanoBananaPro / seedance20")
    p.add_argument("--prompt", help="提示词")
    p.add_argument("--param", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="模型参数 / Model parameter; repeat KEY=VALUE, e.g. imageSize=landscape_16_9")
    p.add_argument("--num", type=int, default=1, help="生成数量 (图片 1-4,视频必为 1)")
    p.add_argument("--resolution", help="resolution / size / imageSize 的快捷参数,预览与生成共用")
    p.add_argument("--duration", help="视频 duration 快捷参数 / Video duration")
    p.add_argument("--mode", help="mode / quality 快捷参数,仅适用于支持它的模型")
    p.add_argument("--rewrite-prompt", action="store_true", help="开启提示词重写 / Enable prompt rewriting")
    p.add_argument("--locale", choices=["zh", "en"], default="zh", help="API response language")
    p.add_argument("--offline", action="store_true", help="--list / --info 使用本地快照,不读 Key、不联网")
    p.add_argument("--dry-run", action="store_true", help="--generate 只校验参数/数量,不联网、不编码媒体、不写文件")
    p.add_argument("--max-coins", type=int, default=0, help="提交前费用预览上限; 0 不设上限 / Pre-submit spending cap")
    p.add_argument("--has-image-input", action="store_true", help="--cost 无素材文件时按有参考图预估")
    p.add_argument("--no-wait", action="store_true", help="--generate 提交后返回任务 ID / Submit and return task ID")
    p.add_argument("--wait-timeout", type=float, default=POLL_TIMEOUT, help="等待超时秒数,可用 --resume 继续")
    p.add_argument("--json", action="store_true", help="生成/恢复时输出 NDJSON 生命周期事件 / Machine-readable events")
    p.add_argument("--image", action="append", default=[],
                   metavar="PATH", help="图生图输入,可重复")
    p.add_argument("--start-frame", metavar="PATH", help="视频起始帧; Seedance 中作为第一张参考图")
    p.add_argument("--end-frame", metavar="PATH", help="Seedance 结束图兼容输入,作为最后一张参考图,不保证严格尾帧")
    p.add_argument("--reference-image", action="append", default=[],
                   metavar="PATH", help="Seedance 视频参考图,与起始/结束图合计最多 4 张")
    p.add_argument("-o", "--output", metavar="PATH",
                   help="输出文件路径。多图时会在 stem 后追加 _1/_2...")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.offline and not (args.list or args.info):
        _die("--offline is only valid with --list or --info; use --generate --dry-run for offline validation.")
    if (args.dry_run or args.no_wait) and not args.generate:
        _die("--dry-run and --no-wait require --generate.")
    if args.has_image_input and not args.cost:
        _die("--has-image-input is only valid with --cost; generation requires actual image inputs.")
    if args.max_coins < 0 or not math.isfinite(args.wait_timeout) or args.wait_timeout <= 0:
        _die("--max-coins must be non-negative and --wait-timeout must be finite and positive.")

    if args.check:
        cmd_check()
        return
    if args.list:
        cmd_list(args.type, args.offline)
        return
    if args.info:
        cmd_info(args.info, args.type, args.offline)
        return
    if args.status:
        cmd_status(args.status)
        return
    if args.resume:
        cmd_resume(args)
        return
    if args.cost:
        if not args.model:
            _die("--cost 需要 --model")
        cmd_cost(args)
        return
    if args.generate:
        if not args.model:
            _die("--generate 需要 --model")
        cmd_generate(args)
        return


if __name__ == "__main__":
    main()
