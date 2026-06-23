# CatsAPI Skill — OpenClaw Skill for CatsAPI (猫影工坊)

[中文](./README.md)

An **Agent Skills**-standard skill pack that lets AI assistants in OpenClaw / Cursor / Claude Code / Codex CLI directly call [CatsAPI (catsapi.com)](https://catsapi.com) for image and video generation.

This version intentionally keeps a compact supported model set:

| Category | Count | Examples |
|---|---:|---|
| Image generation | 5 | GPT Image 2, Nano Banana 2, Nano Banana Pro, FLUX.2 Pro, GrokImage |
| Video generation | 2 | Seedance 2.0, GrokImageVideo |

## Quick Start

### OpenClaw

Just tell OpenClaw:

> Install the catsapi skill from <https://github.com/maodeyu180/OpenClaw_Catsapi_Skill>

### Cursor / Claude Code

```bash
git clone https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git ~/.cursor/skills/catsapi
```

### As a git submodule

```bash
cd your-project/
git submodule add https://github.com/maodeyu180/OpenClaw_Catsapi_Skill.git .cursor/skills/catsapi
git commit -m "Add catsapi skill"
```

## Prerequisites

- **Python 3.8+** (stdlib only, no third-party deps)
- **API Key** — create one at [catsapi.com](https://catsapi.com) → API Key page, format is `cats-xxxxxxxx`
- **Coin balance** — via redemption codes or new-user bonus

## Configuration

```bash
export CATSAPI_API_KEY=cats-your-key
# For self-hosted deployments
export CATSAPI_BASE=http://localhost:8000
```

Self-check:

```bash
python3 scripts/catsapi.py --check
```

## CLI Usage

```bash
# Text-to-image
python3 scripts/catsapi.py --generate --type image \
  --model nanoBananaPro --prompt "an orange cat wearing sunglasses by the sea" \
  --param resolution=2K --param aspectRatio=16:9 -o /tmp/cat.png

# Text-to-video
python3 scripts/catsapi.py --generate --type video \
  --model seedance20 --prompt "a cat walking through a garden" \
  --param resolution=720p --param duration=5 --param aspectRatio=16:9 \
  -o /tmp/cat.mp4

# Cost preview
python3 scripts/catsapi.py --cost --type video --model seedance20 \
  --resolution 720p --duration 10

# List enabled models
python3 scripts/catsapi.py --list --type image
```

## Usage via Agent

After installing the skill, just talk to the agent naturally:

- _"Draw me a puppy playing in the park"_
- _"Turn this image into a video"_
- _"Generate a 4K vertical poster with Nano Banana Pro"_
- _"How many coins do I have?"_
- _"How much would a 10s 720p Seedance 2.0 video cost?"_

The agent infers common parameters such as landscape/portrait/square, 4K, 720p, and 5s/10s from the user's wording, then calls the script with parameters supported by the selected model.

## Project Structure

```
.
├── README.md / README_en.md
├── LICENSE                         # Apache-2.0
├── SKILL.md
├── scripts/
│   ├── catsapi.py
│   └── build_capabilities.py
├── references/
│   ├── api-key-setup.md
│   ├── video-models.md
│   ├── image-models.md
│   └── output-delivery.md
└── data/
    └── capabilities.json
```

> Note: this repo uses a **flat layout** — the repo root IS the skill root,
> `SKILL.md` sits at the top level. Cloning to `~/.cursor/skills/catsapi/`
> (or adding as a submodule at that path) makes Cursor recognize it directly.

## License

Apache License 2.0 — see [LICENSE](./LICENSE).

## Related

- [catsapi.com](https://catsapi.com)
- [Cursor Agent Skills docs](https://cursor.com/docs/skills)
- [Agent Skills open standard](https://agentskills.io)
