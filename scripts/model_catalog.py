"""Client-supported model identities and effective service limits, without prices."""
import re

IMAGE_MODELS = {
    "gptImage2": "GPT Image 2",
    "nanoBanana2": "Nano Banana 2",
    "nanoBananaPro": "Nano Banana Pro",
    "flux2Pro": "FLUX.2 Pro",
    "grokImagineImage": "Grok Imagine Image",
    "seedream5Lite": "Seedream 5 Lite",
    "seedream5Pro": "Seedream 5 Pro",
    "grokImagineImage2": "Grok Imagine Image 2",
}
VIDEO_MODELS = {
    "seedance20": "Seedance 2.0",
    "grokImagineVideo": "Grok Imagine Video",
    "seedance20Mini": "Seedance 2.0 Mini",
    "geminiOmniFlash": "Gemini Omni Flash",
}
DISPLAY_NAMES = {**IMAGE_MODELS, **VIDEO_MODELS}
SUPPORTED_MODELS = {"image": set(IMAGE_MODELS), "video": set(VIDEO_MODELS)}
SEEDANCE_MODELS = {"seedance20", "seedance20Mini"}
# The main-site worker keeps 4 combined image references, despite schema maxFiles=9.
SEEDANCE_REFERENCE_IMAGE_LIMIT = 4
DEFAULT_PROMPT_LIMIT = 2500


def alias_key(value):
    return re.sub(r"[\s_.\-\[\]]+", "", value).lower()


MODEL_ALIASES = {
    alias_key(name): model
    for model, display_name in DISPLAY_NAMES.items()
    for name in (model, display_name)
}
MODEL_ALIASES.update({
    "grokimage": "grokImagineImage",
    "grokimage2": "grokImagineImage2",
    "grokimagevideo": "grokImagineVideo",
    "seedance2": "seedance20",
    "seedance2mini": "seedance20Mini",
})


def client_limits(model, schema):
    image_field = schema.get("imagePrompt", {})
    return {
        "reference_images": (
            SEEDANCE_REFERENCE_IMAGE_LIMIT if model in SEEDANCE_MODELS
            else image_field.get("maxFiles", 1) if image_field
            else 1 if "startFrame" in schema else 0
        ),
        "reference_videos": False,
        "reference_audio": False,
        "strict_end_frame": False,
    }
