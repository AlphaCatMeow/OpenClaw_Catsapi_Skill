#!/usr/bin/env python3
"""
CatsAPI Client — OpenClaw Skill 的统一命令行客户端

支持的动作:
    --check                 验证 API Key + 查询余额
    --list                  列出可用模型 (--type image|video)
    --info MODEL_KEY        查看单个模型的参数定义
    --cost                  费用预览 (--type / --model / --resolution / --duration / --num)
    --generate              提交生成任务并轮询结果 (最常用)
    --status TASK_ID        查询单个任务状态

环境变量:
    CATSAPI_API_KEY         形如 `cats-xxxxxxxx`;未继承环境变量时会尝试读取本地配置
    CATSAPI_BASE            可选,默认 https://catsapi.com

所有输出:
    - 普通信息走 stderr
    - 结构化结果走 stdout (JSON 或单行 `KEY:VALUE`)
    - 任务成功时额外打印 `COST:N` 行 (N 为本次消耗的猫币)
"""
from __future__ import annotations

import argparse
import base64
import json
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

DEFAULT_BASE = "https://catsapi.com"
POLL_INTERVAL = 3
POLL_TIMEOUT = 900  # 15 分钟
API_KEY_ENV = "CATSAPI_API_KEY"
# 默认 Python urllib 的 UA 会被 catsapi.com 前面的 Cloudflare Bot Fight Mode 拦成 403,
# 伪装成浏览器避免被指纹墙误伤。
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
SUPPORTED_MODELS = {
    "image": {
        "gptImage2",
        "nanoBanana2",
        "nanoBananaPro",
        "flux2Pro",
        "grokImagineImage",
    },
    "video": {
        "seedance20",
        "grokImagineVideo",
    },
}
MODEL_ALIASES = {
    "gptImage2": "gptImage2",
    "gptimage2": "gptImage2",
    "nanoBanana2": "nanoBanana2",
    "nanobanana2": "nanoBanana2",
    "nanoBananaPro": "nanoBananaPro",
    "nanobananapro": "nanoBananaPro",
    "flux2Pro": "flux2Pro",
    "flux2pro": "flux2Pro",
    "grokImage": "grokImagineImage",
    "grokimage": "grokImagineImage",
    "grokImagineImage": "grokImagineImage",
    "grokimagineimage": "grokImagineImage",
    "seedance20": "seedance20",
    "seedance2": "seedance20",
    "seedance2.0": "seedance20",
    "grokImageVideo": "grokImagineVideo",
    "grokimagevideo": "grokImagineVideo",
    "grokImagineVideo": "grokImagineVideo",
    "grokimaginevideo": "grokImagineVideo",
}


def _normalize_model(model_key: str | None, task_type: str) -> str | None:
    if not model_key:
        return None
    normalized = MODEL_ALIASES.get(model_key, MODEL_ALIASES.get(model_key.lower(), model_key))
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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
            detail = parsed.get("detail", raw)
        except Exception:
            detail = raw
        _die(f"HTTP {e.code} {method} {path} → {detail}", code=2)
    except urllib.error.URLError as e:
        _die(f"网络错误 {method} {url} → {e.reason}", code=3)

    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _die(f"无法解析 JSON 响应: {raw[:300]}", code=4)
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


def cmd_list(task_type: str) -> None:
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


def cmd_info(model_key: str, task_type: str) -> None:
    model_key = _normalize_model(model_key, task_type) or model_key
    data = _get(f"/api/models?type={urllib.parse.quote(task_type)}")
    for m in data.get("models", []):
        if m["model_key"] == model_key:
            print(json.dumps(m, ensure_ascii=False, indent=2))
            return
    _die(f"模型 `{model_key}` 未在 type={task_type} 的启用列表中。用 --list --type {task_type} 查看")


def cmd_cost(args: argparse.Namespace) -> None:
    args.model = _normalize_model(args.model, args.type)
    body: dict[str, Any] = {
        "model": args.model,
        "task_type": args.type,
        "num_images": args.num,
    }
    if args.resolution:
        body["resolution"] = args.resolution
    if args.duration:
        body["duration"] = args.duration
    if args.mode:
        body["mode"] = args.mode
    if args.rewrite_prompt:
        body["rewrite_prompt"] = True
    data = _post("/api/tasks/cost-preview", body)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_params(raw_params: list[str]) -> dict:
    out: dict[str, Any] = {}
    for item in raw_params or []:
        if "=" not in item:
            _die(f"--param 格式必须是 key=value,收到: {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out


def _encode_image(path: str) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        _die(f"文件不存在: {path}")
    mime, _ = mimetypes.guess_type(p.name)
    if not mime:
        mime = "image/png"
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"name": p.name, "base64": f"data:{mime};base64,{b64}"}


def _download(url: str, out_path: str) -> None:
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp, out.open("wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)
    except Exception as e:
        _die(f"下载失败 {url} → {e}", code=5)


def cmd_generate(args: argparse.Namespace) -> None:
    args.model = _normalize_model(args.model, args.type)
    if args.type == "image" and (args.start_frame or args.end_frame or args.reference_image):
        _die("图片任务请用 --image 传参考图; --start-frame/--end-frame/--reference-image 仅用于视频任务")
    if args.type == "video" and args.image:
        _die("视频任务请用 --start-frame 或 --reference-image 传图片素材,不要用 --image")
    if args.end_frame and args.model != "seedance20":
        _die("当前支持模型中只有 Seedance 2.0 支持 --end-frame")
    if args.reference_image and args.model != "seedance20":
        _die("当前支持模型中只有 Seedance 2.0 支持 --reference-image")
    params = _parse_params(args.param)
    body: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt or "",
        "task_type": args.type,
        "params": params,
        "num_images": args.num,
    }
    if args.image:
        body["images"] = [_encode_image(p) for p in args.image]
    if args.start_frame:
        body.setdefault("files", {})["startFrame"] = _encode_image(args.start_frame)
    if args.end_frame:
        body.setdefault("files", {})["endFrame"] = _encode_image(args.end_frame)
    if args.reference_image:
        body.setdefault("files", {})["referenceImages"] = [
            _encode_image(p) for p in args.reference_image
        ]

    _log(f"[INFO] 提交 {args.type} 任务 model={args.model} ...")
    task = _post("/api/tasks", body)
    task_id = task.get("id")
    if not task_id:
        _die(f"提交失败,返回体: {task}")
    _log(f"[OK] 任务已创建 id={task_id} 预扣 {task.get('cost', 0)} 猫币,开始轮询...")

    start = time.time()
    while True:
        time.sleep(POLL_INTERVAL)
        detail = _get(f"/api/tasks/{task_id}")
        status = detail.get("status", "")
        _log(f"[POLL] {int(time.time()-start)}s status={status}")
        if status == "completed":
            break
        if status == "failed":
            _die(f"任务失败: {detail.get('error_message', '未知错误')}")
        if time.time() - start > POLL_TIMEOUT:
            _die(f"轮询超时 ({POLL_TIMEOUT}s),任务仍在 {status}。稍后用 --status {task_id} 再查")

    cost = detail.get("cost", 0)
    print(f"COST:{cost}")

    # 保存结果
    out_paths: list[str] = []
    if args.type == "video":
        vid = detail.get("result_video") or {}
        url = vid.get("url") or vid.get("videoUrl") or vid.get("video_url")
        if not url:
            _die(f"视频任务完成但未找到 URL,原始 result_video: {vid}")
        out = args.output or f"/tmp/openclaw/catsapi-output/video_{int(time.time())}.mp4"
        _download(url, out)
        out_paths.append(out)
    else:
        imgs = detail.get("result_images") or []
        if not imgs:
            _die("图片任务完成但未返回图片")
        base_out = args.output or f"/tmp/openclaw/catsapi-output/image_{int(time.time())}.png"
        base_p = pathlib.Path(base_out)
        for i, item in enumerate(imgs):
            url = item.get("url") if isinstance(item, dict) else item
            if not url:
                continue
            if len(imgs) == 1:
                target = str(base_p)
            else:
                target = str(base_p.with_stem(f"{base_p.stem}_{i+1}"))
            _download(url, target)
            out_paths.append(target)

    for p in out_paths:
        print(f"OUTPUT_FILE:{p}")
    _log(f"[OK] 完成,共 {len(out_paths)} 个文件,消耗 {cost} 猫币")


def cmd_status(task_id: str) -> None:
    data = _get(f"/api/tasks/{task_id}")
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

    p.add_argument("--type", choices=["image", "video"], default="image",
                   help="任务类型 (默认 image)")
    p.add_argument("--model", help="模型 key,例如 nanoBananaPro / seedance20")
    p.add_argument("--prompt", help="提示词")
    p.add_argument("--param", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="额外参数,可重复,如 --param resolution=1080p --param duration=5")
    p.add_argument("--num", type=int, default=1, help="生成数量 (图片 1-4,视频必为 1)")
    p.add_argument("--resolution", help="费用预览用")
    p.add_argument("--duration", help="费用预览用 (视频)")
    p.add_argument("--mode", help="费用预览用")
    p.add_argument("--rewrite-prompt", action="store_true", help="费用预览: 是否重写提示词")
    p.add_argument("--image", action="append", default=[],
                   metavar="PATH", help="图生图输入,可重复")
    p.add_argument("--start-frame", metavar="PATH", help="视频起始帧")
    p.add_argument("--end-frame", metavar="PATH", help="视频结束帧")
    p.add_argument("--reference-image", action="append", default=[],
                   metavar="PATH", help="视频参考图,可重复。Seedance 2.0 最多 4 张")
    p.add_argument("-o", "--output", metavar="PATH",
                   help="输出文件路径。多图时会在 stem 后追加 _1/_2...")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.check:
        cmd_check()
        return
    if args.list:
        cmd_list(args.type)
        return
    if args.info:
        cmd_info(args.info, args.type)
        return
    if args.status:
        cmd_status(args.status)
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
