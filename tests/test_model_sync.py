"""Offline regression tests; no API keys, network calls, or generation charges."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_capabilities as builder
import catsapi as client


class ModelSyncTests(unittest.TestCase):
    def setUp(self):
        self.capabilities = json.loads((ROOT / "data/capabilities.json").read_text())
        # Any unexpected HTTP request must fail before credential discovery.
        self.network = patch.object(client, "_request", side_effect=AssertionError("network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def args(self, model, *extra):
        kind = "video" if model in client.SUPPORTED_MODELS["video"] else "image"
        return client.build_parser().parse_args([
            "--generate", "--type", kind, "--model", model, "--prompt", "test", *extra,
        ])

    def body(self, model, *extra):
        with patch.object(client, "_encode_image", side_effect=lambda name: {"name": name}):
            return client._build_generation_body(self.args(model, *extra))

    def assert_rejected(self, model, *extra):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.body(model, *extra)

    def test_supported_sets_and_defaults(self):
        self.assertEqual(len(client.SUPPORTED_MODELS["image"]), 9)
        self.assertEqual(len(client.SUPPORTED_MODELS["video"]), 4)
        for kind in ("image", "video"):
            models = self.capabilities[f"{kind}_models"]
            self.assertEqual(set(models), client.SUPPORTED_MODELS[kind])
            for model in models.values():
                self.assertNotIn("_meta", model["params"])
                for field in model["params"].values():
                    if field.get("options") and "default" in field:
                        self.assertIn(field["default"], field["options"])
        self.assertEqual(builder.SUPPORTED_IMAGE_MODELS, client.SUPPORTED_MODELS["image"])
        self.assertEqual(builder.SUPPORTED_VIDEO_MODELS, client.SUPPORTED_MODELS["video"])

    def test_metadata_is_not_a_parameter(self):
        schema = {"_meta": {"max_chars": 2200}, "max_input_tokens": 200,
                  "mode": {"options": {"keys": ["fast"]}, "default": "fast"}}
        self.assertEqual(set(builder._extract_param_schema(schema)), {"mode"})
        self.assertEqual(builder._extract_limits(schema), {"max_chars": 2200, "max_input_tokens": 200})

    def test_api_builder_preserves_prompt_limit(self):
        responses = [
            io.BytesIO(json.dumps({"models": [{"model_key": "gptImage2", "max_prompt_chars": 10000,
                                               "params_schema": {}}]}).encode()),
            io.BytesIO(b'{"models": []}'),
        ]
        with patch.object(builder.urllib.request, "urlopen", side_effect=responses):
            result = builder._build_from_api("https://example.invalid")
        self.assertEqual(result["image_models"]["gptImage2"]["limits"], {"max_chars": 10000})

    def test_new_gpt_sizes_and_reference_limits(self):
        sizes = self.capabilities["image_models"]["gptImage2"]["params"]["size"]["options"]
        self.assertEqual(len(sizes), 20)
        for size in ("1280x1024", "2688x1152", "3824x2144"):
            self.assertEqual(self.body("gptImage2", "--param", f"size={size}")["params"]["size"], size)
        for model, count in (("gptImage25", 16), ("gptImage2", 16), ("nanoBanana2", 14), ("nanoBananaPro", 4),
                             ("flux2Pro", 3), ("grokImagineImage", 1), ("seedream5Lite", 4),
                             ("seedream5Pro", 4), ("grokImagineImage2", 1)):
            refs = [value for i in range(count) for value in ("--image", f"ref-{i}.png")]
            self.assertEqual(len(self.body(model, *refs)["images"]), count)
            self.assert_rejected(model, *refs, "--image", "extra.png")

    def test_web_search_false_is_a_boolean(self):
        for model in ("nanoBanana2", "nanoBananaPro"):
            body = self.body(model, "--param", "enableWebSearch=false")
            self.assertIs(body["params"]["enableWebSearch"], False)

    def test_gpt25_aliases_defaults_and_parameter_limits(self):
        for alias in ("GPT Image 2.5", "gpt-image-2.5", "gptImage25"):
            self.assertEqual(client._normalize_model(alias, "image"), "gptImage25")
        self.assertEqual(self.body("gptImage25")["params"], {
            "size": "1024x1024", "quality": "auto", "variant": "flare",
            "background": "auto", "rewritePrompt": False,
        })
        capability = self.capabilities["image_models"]["gptImage25"]
        self.assertEqual(capability["params"]["quality"]["options"],
                         ["low", "auto", "medium", "high", "xhigh", "max"])
        self.assertEqual(capability["client_limits"]["reference_images"], 16)
        for size in capability["params"]["size"]["options"]:
            for quality in capability["params"]["quality"]["options"]:
                self.body("gptImage25", "--resolution", size, "--mode", quality)
        self.body("gptImage25", "--prompt", "x" * 10000)
        self.assert_rejected("gptImage25", "--prompt", "x" * 10001)
        for param in ("variant=thinking", "background=invalid", "quality=mid", "size=auto"):
            self.assert_rejected("gptImage25", "--param", param)
        self.assert_rejected("gptImage25", "--num", "5")

    def test_seedance_reference_mode_and_legacy_input_order(self):
        body = self.body("seedance20", "--start-frame", "start.png",
                         "--reference-image", "ref1.png", "--reference-image", "ref2.png",
                         "--end-frame", "end.png")
        self.assertEqual(body["params"]["inputMode"], "reference")
        self.assertEqual(list(body["files"]), ["referenceImages"])
        self.assertEqual([item["name"] for item in body["files"]["referenceImages"]],
                         ["start.png", "ref1.png", "ref2.png", "end.png"])
        text_only = self.body("seedance20")
        self.assertNotIn("files", text_only)
        self.assertEqual(text_only["params"]["inputMode"], "reference")

    def test_seedance_rejects_effective_limit_and_unsupported_mode(self):
        refs = [value for i in range(4) for value in ("--reference-image", f"ref-{i}.png")]
        self.assert_rejected("seedance20", *refs, "--start-frame", "extra.png")
        self.assert_rejected("seedance20", "--param", "inputMode=standard")
        self.assert_rejected("seedance20", "--prompt", "x" * 2201)
        self.assert_rejected("seedance20", "--num", "2")

    def test_grok_keeps_start_frame_and_rejects_end_frame(self):
        self.assertEqual(self.body("grokImagineVideo", "--start-frame", "start.png")["files"],
                         {"startFrame": {"name": "start.png"}})
        self.assert_rejected("grokImagineVideo", "--end-frame", "end.png")
        self.assert_rejected("gptImage2", "--param", "size=invalid")

    def test_mocked_generation_delivery_and_failure(self):
        for model, detail, output in (
            ("gptImage2", {"result_images": [{"url": "https://example.invalid/image.png"}]}, "result.png"),
            ("seedance20", {"result_video": {"url": "https://example.invalid/video.mp4"}}, "result.mp4"),
        ):
            result = {"id": "mock-task", "status": "completed", "cost": 12, **detail}
            with patch.object(client, "_post", side_effect=[{"total_cost": 12, "sufficient": True},
                                                           {"id": "mock-task"}]) as submit, \
                 patch.object(client, "_get", return_value=result), \
                 patch.object(client.time, "sleep"), patch.object(client, "_download") as download, \
                 contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()):
                client.cmd_generate(self.args(model, "-o", output))
            self.assertEqual([call.args[0] for call in submit.call_args_list],
                             ["/api/tasks/cost-preview", "/api/tasks"])
            download.assert_called_once()
            self.assertIn("COST:12", stdout.getvalue())
            self.assertIn(f"OUTPUT_FILE:{Path(output).resolve()}", stdout.getvalue())
        with patch.object(client, "_post", side_effect=[{"total_cost": 12, "sufficient": True},
                                                       {"id": "mock-task"}]), \
             patch.object(client, "_get", return_value={"status": "failed", "error_message": "mock failure"}), \
             patch.object(client.time, "sleep"), patch.object(client, "_download") as download, \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            client.cmd_generate(self.args("seedance20"))
        download.assert_not_called()

    def test_seedream_and_grok2_schema_and_friendly_aliases(self):
        for key, name in (("seedream5Lite", "Seedream 5 Lite"), ("seedream5Pro", "Seedream 5 Pro")):
            self.assertEqual(client._normalize_model(name, "image"), key)
            body = self.body(key, "--resolution", "landscape_16_9", "--param", "seed=0", "--num", "4")
            self.assertEqual(body["params"], {"imageSize": "landscape_16_9", "rewritePrompt": False, "seed": 0})
            self.assert_rejected(key, "--param", "aspectRatio=16:9")
            self.assert_rejected(key, "--param", "resolution=2K")
        self.assertEqual(client._normalize_model("Grok Imagine Image 2", "image"), "grokImagineImage2")
        self.assertEqual(self.body("grokImagineImage2")["params"], {"aspectRatio": "1:1", "rewritePrompt": False})

    def test_mini_and_omni_do_not_inherit_unsupported_fields(self):
        for key, name in (("seedance20Mini", "Seedance 2.0 Mini"), ("geminiOmniFlash", "Gemini Omni Flash")):
            self.assertEqual(client._normalize_model(name, "video"), key)
            self.assertNotIn("mode", self.body(key)["params"])
            self.assert_rejected(key, "--mode", "fast")
        mini = self.body("seedance20Mini", "--start-frame", "start.png", "--end-frame", "end.png")
        self.assertEqual([v["name"] for v in mini["files"]["referenceImages"]], ["start.png", "end.png"])
        self.assertEqual(mini["params"]["resolution"], "480p")
        self.assertEqual(mini["params"]["duration"], "8")
        self.assert_rejected("seedance20Mini", "--prompt", "x" * 2201)
        refs = [value for i in range(5) for value in ("--reference-image", f"{i}.png")]
        self.assert_rejected("seedance20Mini", *refs)
        omni = self.body("geminiOmniFlash", "--start-frame", "start.png")
        self.assertEqual(omni["params"], {"duration": "5", "aspectRatio": "16:9", "rewritePrompt": False})
        self.assertEqual(omni["files"], {"startFrame": {"name": "start.png"}})
        self.assert_rejected("geminiOmniFlash", "--resolution", "720p")
        self.assert_rejected("geminiOmniFlash", "--duration", "4")
        self.assert_rejected("geminiOmniFlash", "--duration", "11")
        self.assert_rejected("geminiOmniFlash", "--param", "aspectRatio=1:1")

    def test_invalid_params_fail_locally(self):
        for params in (("seed=nan",), ("seed=inf",), ("rewritePrompt=0",), ("imagePrompt=path.png",),
                       ("unknown=1",), ("numImages=2",), ("seed=1", "seed=2")):
            extra = [value for param in params for value in ("--param", param)]
            self.assert_rejected("seedream5Pro", *extra)
        self.assert_rejected("gptImage2", "--resolution", "1024x1024", "--param", "size=1536x1024")
        self.assert_rejected("flux2Pro", "--num", "2")
        self.assert_rejected("seedream5Lite", "--prompt", "x" * 2501)

    def test_all_defaults_build_without_credentials(self):
        for kind, models in client.SUPPORTED_MODELS.items():
            for model in models:
                body = self.body(model, "--locale", "en")
                self.assertEqual(body["task_type"], kind)
                self.assertEqual(body["locale"], "en")
                self.assertFalse(body["params"]["rewritePrompt"])


if __name__ == "__main__":
    unittest.main()
