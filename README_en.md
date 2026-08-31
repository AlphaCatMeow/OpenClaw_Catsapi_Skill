# CatsAPI Agent Skill

[中文](README.md)

Generate and edit images, and generate videos through [CatsAPI](https://catsapi.com) in Agent Skills-compatible hosts. The Skill handles intent and delivery; a standard-library Python CLI validates parameters, previews cost, submits tasks, and resumes existing ones.

## Supported Models

| Type | Model key | Name |
| --- | --- | --- |
| Image | `gptImage2` | GPT Image 2 |
| Image | `nanoBanana2` | Nano Banana 2 |
| Image | `nanoBananaPro` | Nano Banana Pro |
| Image | `flux2Pro` | FLUX.2 Pro |
| Image | `grokImagineImage` | GrokImage |
| Image | `seedream5Lite` | Seedream 5 Lite |
| Image | `seedream5Pro` | Seedream 5 Pro |
| Image | `grokImagineImage2` | Grok Imagine Image 2 |
| Video | `seedance20` | Seedance 2.0 |
| Video | `grokImagineVideo` | GrokImageVideo |
| Video | `seedance20Mini` | Seedance 2.0 Mini |
| Video | `geminiOmniFlash` | Gemini Omni Flash |

8 image and 4 video models. Display names also work, for example `--model "Seedance 2.0 Mini"`. Client support does not guarantee live availability; use `--list` to check the service.

## Installation and Configuration

The repository root is the Skill root, with [SKILL.md](SKILL.md) as its entry point. Clone into a Skill directory supported by your host and enable it there, or keep a standalone checkout and register that directory with your host:

```bash
git clone https://github.com/maodeyu180/CatsAPI-Agent-Skill.git catsapi
```

In OpenClaw, you can also ask the assistant to install `catsapi` from this repository. A Git submodule in the main-site repository is not required.

The CLI requires Python 3.8+ and no third-party packages. Create a key in your CatsAPI account and ensure you have sufficient balance. Do not paste the full key into chat. Use environment variables or a private local configuration file; see [key setup](references/api-key-setup.md).

```bash
export CATSAPI_API_KEY=cats-your-key
# Override only for self-hosted deployments; default is https://catsapi.com
export CATSAPI_BASE=http://localhost:8000

python3 scripts/catsapi.py --check
```

## Agent Workflow

Describe your request naturally:

- “Use Seedream 5 Pro to change this product photo to a white background; keep everything else.”
- “Quote a 6-second portrait video with Gemini Omni Flash. Do not generate it yet.”
- “Generate two square images with Grok Imagine Image 2, within the quote I approve.”
- “The previous task timed out. Resume that task; do not generate again.”

The assistant distinguishes queries, generation, editing, and recovery. It does not force a model menu, alter text you asked to preserve, or silently upgrade resolution. It validates parameters and checks a live quote before generation. Batch, video, or significant cost upgrades need an agreed budget.

Every submission checks a fresh quote, balance, and `--max-coins`. This is a pre-submit guard, **not an atomic server-side price lock**; 0 means no cap. After a timeout, disconnect, or download failure, retain the task ID and use `--resume`, not another generation request.

## CLI Examples

These queries and previews do not create paid generation tasks. `--cost` uses the network; offline commands do not read credentials:

```bash
python3 scripts/catsapi.py --list --type image --offline
python3 scripts/catsapi.py --info geminiOmniFlash --type video --offline

python3 scripts/catsapi.py --generate --type image \
  --model seedream5Lite --prompt "an orange cat by a window" \
  --param imageSize=landscape_16_9 --locale en --dry-run

python3 scripts/catsapi.py --cost --type video \
  --model seedance20Mini --resolution 720p --duration 6
```

`--dry-run` checks parameters and counts, but not media contents or live availability; it writes no files. For real generation, remove it and set an accepted spending cap:

```bash
# Replace N with the user's approved coin limit; this submits a paid task
python3 scripts/catsapi.py --generate --type video \
  --model geminiOmniFlash --prompt "an orange cat walking through a garden" \
  --duration 6 --param aspectRatio=9:16 --locale en \
  --max-coins N --no-wait --json

# Resume using the returned ID; this never creates another task
python3 scripts/catsapi.py --resume TASK_ID --json
```

Downloads default to `catsapi-output/` under the current working directory. Set a filename with `-o`; existing files receive numbered alternatives instead of being overwritten. Hosts deliver results through native attachments, media previews, or local file links, without requiring a specific `message` tool.

See the [CLI reference](references/cli-reference.md) for flags, JSON events, and recovery.

## Parameters and Input Limits

- GPT Image 2: 20 sizes and up to 16 reference images. Nano Banana 2: up to 14. Nano Banana 2 / Pro enable web search by default; disable it with `--param enableWebSearch=false`.
- Seedream 5 Lite / Pro: `imageSize`, up to 4 references, optional numeric `seed`. No independent `resolution`, `quality`, or `aspectRatio` fields.
- Grok Imagine Image 2: `aspectRatio` and one reference image. It is distinct from GrokImage.
- Seedance 2.0 / Mini: reference mode, 480p, 8 seconds by default. Mini has no `mode`; do not pass `fast`.
- Both Seedance models merge start → references → end, with at most 4 images total. These are references, not guaranteed first/last frames. The schema lists 9, but the main-site worker currently keeps only 4, so the CLI enforces the effective limit.
- Gemini Omni Flash: 5–10 seconds, 16:9 / 9:16, optional single start image. No resolution or quality controls.
- Image inputs must be JPG / PNG / WEBP, at most 10 MB each. This CLI does not expose video or audio reference inputs.

See [image models](references/image-models.md), [video models](references/video-models.md), and [parameter inference](references/parameter-inference.md).

## Maintenance and Validation

`scripts/model_catalog.py` is the central allowlist and alias registry. Rebuild the capability snapshot from the main site instead of maintaining another price table:

```bash
python3 scripts/build_capabilities.py \
  --image-models /path/to/backend/app/image_models.json \
  --video-models /path/to/backend/app/abacus_video_models.json \
  -o data/capabilities.json
```

Alternatively, use `--from-api https://catsapi.com -o data/capabilities.json` to read the public live schema. Use a fresh `--cost` response for pricing.

Run `python -m unittest discover -s tests -v` in a project Python environment. Tests mock media and networking and cover model support, request parameters, spending guards, offline validation, recovery, and delivery. They do not read real keys or create paid tasks, and do not replace live model-output testing.

See the [design notes](docs/skill-design.md) for the workflow references and tradeoffs. The repository separates the entry point (`SKILL.md`), detailed guidance (`references/`), implementation (`scripts/`), snapshot (`data/`), and offline tests (`tests/`).

## Related Projects and License

- [CatsAPI main site](https://catsapi.com)
- [ComfyUI_Catsapi](https://github.com/maodeyu180/ComfyUI_Catsapi) — ComfyUI nodes for the same service
- [Apache License 2.0](LICENSE)
