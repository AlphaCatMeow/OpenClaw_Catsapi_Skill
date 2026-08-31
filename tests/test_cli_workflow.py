"""Offline intent/CLI workflow regressions. Never use real credentials or HTTP."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import catsapi as client


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        for name in ("_api_key",):
            mock = patch.object(client, name, side_effect=AssertionError("real credentials forbidden"))
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(client.urllib.request, "urlopen", side_effect=AssertionError("network forbidden"))
        mock.start()
        self.addCleanup(mock.stop)

    def run_cli(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            client.main(list(argv))
        return out.getvalue()

    def test_offline_discovery_needs_no_credentials(self):
        for kind, count in (("image", 8), ("video", 4)):
            data = json.loads(self.run_cli("--list", "--type", kind, "--offline"))
            self.assertEqual(len(data["models"]), count)
            self.assertFalse(data["live_availability_checked"])
        info = json.loads(self.run_cli("--info", "Seedance 2.0 Mini", "--type", "video", "--offline"))
        self.assertEqual(info["client_limits"]["reference_images"], 4)

    def test_dry_run_preserves_prompt_and_never_encodes_or_writes(self):
        with patch.object(client, "_encode_image", side_effect=AssertionError("encoding forbidden")), \
             patch.object(client, "_download", side_effect=AssertionError("download forbidden")), \
             patch.object(client.pathlib.Path, "mkdir", side_effect=AssertionError("write forbidden")):
            data = json.loads(self.run_cli("--generate", "--model", "Seedream 5 Pro", "--prompt", "标题：猫 与 Coffee",
                                          "--image", "not-present.png", "--locale", "en", "--num", "2", "--dry-run"))
        self.assertEqual(data["request"]["prompt"], "标题：猫 与 Coffee")
        self.assertEqual(data["request"]["images"], [{"name": "not-present.png"}])
        self.assertEqual(data["request"]["locale"], "en")
        self.assertEqual(data["cost_preview_request"]["num_images"], 2)
        self.assertTrue(data["cost_preview_request"]["has_image_input"])

    def test_cost_query_never_submits_and_uses_effective_params(self):
        cases = [
            ("image", "gptImage2", ["--resolution", "2688x1152", "--mode", "high", "--num", "3"],
             {"resolution": "2688x1152", "mode": "high", "num_images": 3}),
            ("image", "seedream5Lite", ["--param", "imageSize=portrait_16_9"], {"resolution": "portrait_16_9"}),
            ("video", "seedance20Mini", ["--param", "resolution=720p", "--duration", "6"],
             {"resolution": "720p", "duration": "6"}),
            ("video", "geminiOmniFlash", ["--duration", "10"], {"duration": "10"}),
        ]
        for kind, model, args, expected in cases:
            with patch.object(client, "_post", return_value={"total_cost": 7}) as post:
                self.run_cli("--cost", "--type", kind, "--model", model, "--has-image-input", *args)
            post.assert_called_once()
            self.assertEqual(post.call_args.args[0], "/api/tasks/cost-preview")
            payload = post.call_args.args[1]
            self.assertTrue(payload["has_image_input"])
            for key, value in expected.items():
                self.assertEqual(payload[key], value)
            if model in {"seedance20Mini", "geminiOmniFlash"}:
                self.assertNotIn("mode", payload)
            if model == "geminiOmniFlash":
                self.assertNotIn("resolution", payload)

    def test_spending_guard_fails_closed_before_task_creation(self):
        previews = [{}, {"total_cost": True, "sufficient": True}, {"total_cost": "5", "sufficient": True},
                    {"total_cost": -1, "sufficient": True}, {"total_cost": float("nan"), "sufficient": True},
                    {"total_cost": 3}, {"total_cost": 3, "sufficient": False},
                    {"total_cost": 11, "sufficient": True}]
        for preview in previews:
            with self.subTest(preview=preview), patch.object(client, "_post", return_value=preview) as post, \
                 self.assertRaises(SystemExit):
                self.run_cli("--generate", "--model", "grokImagineImage2", "--prompt", "test", "--max-coins", "10")
            post.assert_called_once()
            self.assertEqual(post.call_args.args[0], "/api/tasks/cost-preview")

    def test_no_wait_submits_once_and_flushes_json_receipt(self):
        with patch.object(client, "_post", side_effect=[{"total_cost": 8, "sufficient": True}, {"id": "task-1"}]) as post, \
             patch.object(client, "_get", side_effect=AssertionError("no polling")), \
             patch.object(client, "_download", side_effect=AssertionError("no download")):
            result = json.loads(self.run_cli("--generate", "--type", "video", "--model", "geminiOmniFlash",
                                            "--prompt", "test", "--max-coins", "8", "--no-wait", "--json"))
        self.assertEqual(result["event"], "submitted")
        self.assertEqual(result["task_id"], "task-1")
        self.assertEqual(result["estimated_cost"], 8)
        self.assertEqual([call.args[0] for call in post.call_args_list], ["/api/tasks/cost-preview", "/api/tasks"])
        self.assertNotIn("resolution", post.call_args_list[1].args[1]["params"])

    def test_resume_downloads_without_preview_or_submission(self):
        detail = {"status": "completed", "task_type": "video", "result_video": {"url": "https://example.invalid/video"}}
        with patch.object(client, "_get", return_value=detail) as get, \
             patch.object(client, "_post", side_effect=AssertionError("resume never posts")), \
             patch.object(client, "_download") as download:
            events = [json.loads(line) for line in self.run_cli("--resume", "task-1", "--json").splitlines()]
        self.assertEqual([item["event"] for item in events], ["resuming", "completed"])
        self.assertIsNone(events[1]["cost"])
        self.assertTrue(Path(events[1]["output_files"][0]).is_absolute())
        get.assert_called_once_with("/api/tasks/task-1")
        download.assert_called_once()

    def test_timeout_keeps_task_id_and_does_not_resubmit(self):
        with patch.object(client, "_get", return_value={"status": "processing"}), \
             patch.object(client, "_post", side_effect=AssertionError("no post")), \
             patch.object(client.time, "monotonic", side_effect=[0, 2]), \
             contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err, \
             self.assertRaises(SystemExit) as raised:
            client.main(["--resume", "task-2", "--wait-timeout", "1", "--json"])
        self.assertEqual(raised.exception.code, 6)
        self.assertIn("task-2", out.getvalue())
        self.assertIn("--resume task-2", err.getvalue())

    def test_download_failure_does_not_resubmit(self):
        detail = {"status": "completed", "result_images": [{"url": "https://example.invalid/image"}]}
        with patch.object(client, "_get", return_value=detail), \
             patch.object(client, "_post", side_effect=AssertionError("no post")), \
             patch.object(client, "_download", side_effect=SystemExit(5)), self.assertRaises(SystemExit):
            self.run_cli("--resume", "task-3")

    def test_unknown_submission_never_retries(self):
        for failure in (urllib.error.URLError("test"), TimeoutError("test"), OSError("test")):
            with patch.object(client, "_api_key", return_value="cats-test-only"), \
                 patch.object(client.urllib.request, "urlopen", side_effect=failure) as request, \
                 contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
                client._post("/api/tasks", {"model": "seedream5Lite"})
            request.assert_called_once()
            self.assertIn("unknown", err.getvalue())
            self.assertNotIn("cats-test-only", err.getvalue())

    def test_invalid_submission_response_is_not_printed_or_retried(self):
        for response in (b"<html>private upstream diagnostics</html>", b"[]"):
            with patch.object(client, "_api_key", return_value="cats-test-only"), \
                 patch.object(client.urllib.request, "urlopen", return_value=io.BytesIO(response)) as request, \
                 contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
                client._post("/api/tasks", {})
            request.assert_called_once()
            self.assertIn("unknown", err.getvalue())
            self.assertNotIn("private upstream", err.getvalue())

    def test_output_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "result.png"
            target.write_bytes(b"original")
            alternative = client._available_output(target)
            self.assertEqual(alternative.name, "result_1.png")
            with patch.object(client.urllib.request, "urlopen", return_value=io.BytesIO(b"new image")), \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                client._download("https://example.invalid/image", str(target))
            self.assertEqual(target.read_bytes(), b"original")
            with patch.object(client.urllib.request, "urlopen", return_value=io.BytesIO(b"<html>challenge</html>")), \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                client._download("https://example.invalid/image", str(alternative))
            self.assertFalse(alternative.exists())
            with patch.object(client.urllib.request, "urlopen", return_value=io.BytesIO(b"valid mock media")):
                client._download("https://example.invalid/image", str(alternative))
            self.assertEqual(alternative.read_bytes(), b"valid mock media")

    def test_invalid_flags_or_output_directory_fail_before_network(self):
        for args in (("--cost", "--model", "gptImage2", "--dry-run"), ("--resume", "x", "--no-wait"),
                     ("--check", "--offline"), ("--resume", "x", "--wait-timeout", "nan"),
                     ("--generate", "--model", "gptImage2", "--prompt", "test", "--max-coins", "-1"),
                     ("--generate", "--model", "gptImage2", "--prompt", "test", "--has-image-input"),
                     ("--generate", "--model", "gptImage2", "--prompt", "test", "-o", str(ROOT))):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.run_cli(*args)


if __name__ == "__main__":
    unittest.main()
