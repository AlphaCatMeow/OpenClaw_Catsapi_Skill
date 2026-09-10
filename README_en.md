# CatsAPI Agent Skill

[中文](README.md)

Generate and edit images, and generate videos through [CatsAPI](https://catsapi.com) in Agent Skills-compatible hosts. The Skill handles intent and delivery; a standard-library Python CLI validates parameters, previews cost, submits tasks, and resumes existing ones.

## Compatible Agents

This is not an OpenClaw-only plugin. The project uses the [Agent Skills](https://agentskills.io/home) structure of `SKILL.md` plus scripts and references. It targets agents that can read skills, execute Python, and access the network, regardless of which language model powers the host.

The following agents document Skill support and are integration targets. **This list verifies host capabilities and installation locations, not end-to-end testing of CatsAPI on every client, version, or runtime.** Official documentation checked on 2026-08-31; follow the agent links for installation details.

| Agent | Project / workspace location | User-level location |
| --- | --- | --- |
| [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/) | `.hermes/skills/catsapi/` (requires project trust) | `~/.hermes/skills/catsapi/` |
| [OpenClaw](https://docs.openclaw.ai/tools/skills) | `<workspace>/skills/catsapi/` | `~/.openclaw/skills/catsapi/` |
| [Claude Code](https://code.claude.com/docs/en/skills) | `.claude/skills/catsapi/` | `~/.claude/skills/catsapi/` |
| [Codex (CLI / IDE / local desktop tasks)](https://developers.openai.com/codex/skills/) | `.agents/skills/catsapi/` | `~/.agents/skills/catsapi/` |
| [Cursor Agent](https://cursor.com/docs/skills) | `.cursor/skills/catsapi/` | `~/.cursor/skills/catsapi/` |
| [Gemini CLI](https://geminicli.com/docs/cli/skills/) | `.gemini/skills/catsapi/` | `~/.gemini/skills/catsapi/` |
| [OpenCode](https://opencode.ai/docs/skills/) | `.opencode/skills/catsapi/` | `~/.config/opencode/skills/catsapi/` |
| [GitHub Copilot (CLI / IDE agent mode)](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) | `.github/skills/catsapi/` | `~/.copilot/skills/catsapi/` |
| [Cline](https://docs.cline.bot/customization/skills) | `.cline/skills/catsapi/` | `~/.cline/skills/catsapi/` |
| [Windsurf / Devin Desktop (Cascade)](https://docs.devin.ai/desktop/cascade/skills) | `.windsurf/skills/catsapi/` | `~/.codeium/windsurf/skills/catsapi/` |

These are common locations, not exhaustive search paths. Custom profiles, remote machines, and containers follow the host's configuration. Keep the installed directory named `catsapi` to match the `name` in `SKILL.md`. Install the complete repository, not just `SKILL.md`, so scripts, model snapshots, and references remain available.

Other Agent Skills-compatible agents should also be able to integrate it. Agents without a native Skill loader can read the entry point and invoke the CLI manually, but require their own directory mapping and trigger instructions. The full workflow also requires:

- Python 3.8+, a CatsAPI key, and network access to CatsAPI and result download URLs in the environment where the agent actually executes commands.
- Permission to read input media, execute scripts, and write output files, subject to the host's trust, sandbox, and approval rules. Read-only or chat-only modes cannot run generation directly.
- Host-appropriate delivery through attachments, media previews, or file links. Without image-viewing capabilities, an agent must not claim visual verification.

## Supported Models

| Type | Model key | Name |
| --- | --- | --- |
| Image | `gptImage25` | GPT Image 2.5 |
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

9 image and 4 video models. Display names also work, for example `--model "GPT Image 2.5"`. Client support does not guarantee live availability; use `--list` to check the service.

## Installation and Configuration

The repository root is the Skill root, with [SKILL.md](SKILL.md) as its entry point. Clone into a Skill directory supported by your host and enable it there, or keep a standalone checkout and register that directory with your host:

```bash
git clone https://github.com/maodeyu180/CatsAPI-Agent-Skill.git catsapi
```

Place the complete directory in a location from the table, or use the host's official installer or directory-linking feature, then confirm that `catsapi` is discovered and enabled. Project-level Hermes installations also require trusting the project as described in its documentation. A Git submodule in the main-site repository is not required.

Cross-host note: the entry point retains OpenClaw's `metadata.openclaw` and `{baseDir}` notation. `{baseDir}` means the absolute directory containing `SKILL.md`, not a shell variable. If the host does not expand it, replace the placeholder in commands with the real directory and quote paths containing spaces. If a host strictly rejects nested OpenClaw metadata, remove that optional entry only from the installed copy; the CLI does not depend on it. No generation logic changes are needed, and you should not change the working directory just to run the script.

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

- GPT Image 2 / 2.5: 20 sizes and up to 16 reference images. 2.5 supports 1–4 outputs and defaults to Flare / auto / 1024x1024. Quality options are ordered `low / auto / medium / high / xhigh / max`; prompts allow up to 10,000 characters.
- For 2.5, select the precise variant with `--param variant=sunburst` and transparent PNG output with `--param background=transparent` (auto / opaque are also available). At the same quality and size, CatsAPI prices Sunburst at 1.25 times Flare per image, rounded to a whole coin. The CLI sends the variant for a server quote and checks `--max-coins`; it does not apply another local multiplier.
- Nano Banana 2 accepts up to 14 references. Nano Banana 2 / Pro enable web search by default; disable it with `--param enableWebSearch=false`.
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
