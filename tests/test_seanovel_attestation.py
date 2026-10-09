"""Offline client/server regression tests for the Mangaro SeaNovel HMAC protocol.

Runs against a temporary loopback HTTP server. No requests to SeaNovel or Vercel,
no production credentials, and no changes to publishing or Android components.
"""
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from validate import build  # noqa: E402
import sea_attestation as client  # noqa: E402

PROBE = ROOT / "vercel-seanovel" / "api" / "probe.py"
spec = importlib.util.spec_from_file_location("seanovel_vercel_probe_test", PROBE)
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

FAKE_KEY = "a" * 64  # TEST ONLY; never use as a real credential.


def healthy_probe(selectors=None):
    if not isinstance(selectors, dict) or not selectors.get("text"):
        raise ValueError("Missing test selector")
    return {
        "domain": "seanovel.org",
        "status": "healthy",
        "catalog": True,
        "search": True,
        "details": True,
        "chapters": True,
        "text": True,
        "catalog_count": 3,
        "chapter_count": 5,
        "paragraphs": 6,
        "text_characters": 900,
    }


class LocalHandler(server_module.handler):
    tamper = "none"

    def log_message(self, *args):
        pass

    def reply(self, status, data):
        if status == 200 and isinstance(data, dict) and "signature" in data:
            data = dict(data)
            tamper = type(self).tamper
            if tamper == "bad_signature":
                data["signature"] = "0" * 64
            elif tamper != "none":
                payload = json.loads(base64.b64decode(data["payload"]))
                if tamper == "wrong_nonce":
                    payload["nonce"] = "0" * 64
                elif tamper == "stale":
                    payload["timestamp"] = payload["requestedAt"] - 121
                elif tamper == "wrong_digest":
                    payload["candidateSha256"] = "0" * 64
                elif tamper == "wrong_revision":
                    payload["revision"] += 1
                elif tamper == "wrong_domain":
                    payload["result"]["domain"] = "example.invalid"
                elif tamper == "failed_stage":
                    payload["result"]["text"] = False
                elif tamper == "invalid_counts":
                    payload["result"]["catalog_count"] = 0
                else:
                    raise AssertionError("Unknown tamper mode")
                raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
                data["payload"] = base64.b64encode(raw).decode()
                data["signature"] = hmac.new(
                    FAKE_KEY.encode(), b"response-v1\n" + raw, hashlib.sha256
                ).hexdigest()
        return super().reply(status, data)


class SeaNovelAttestationSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:%d/api/probe" % cls.httpd.server_port

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        LocalHandler.tamper = "none"
        self.bundle = build(2)
        self.environment = patch.dict(
            os.environ, {"SEANOVEL_ATTESTATION_SECRET": FAKE_KEY}
        )
        self.environment.start()
        self.url_override = patch.object(client, "URL", self.url)
        self.url_override.start()
        self.probe_override = patch.object(server_module, "run_checks", healthy_probe)
        self.probe_override.start()

    def tearDown(self):
        self.probe_override.stop()
        self.url_override.stop()
        self.environment.stop()
        LocalHandler.tamper = "none"

    def test_valid_signed_request_and_response(self):
        result = client.check(self.bundle)
        self.assertIs(result["attestationVerified"], True)
        self.assertEqual(result["domain"], "seanovel.org")
        self.assertEqual(result["revision"], 2)

    def test_request_without_valid_hmac_is_rejected(self):
        original_post = requests.post

        def invalid_request(*args, **kwargs):
            headers = dict(kwargs["headers"])
            headers["Authorization"] = "HMAC-SHA256 " + "0" * 64
            kwargs["headers"] = headers
            return original_post(*args, **kwargs)

        with patch.object(client.requests, "post", side_effect=invalid_request):
            with self.assertRaises(requests.HTTPError) as captured:
                client.check(self.bundle)
        self.assertEqual(captured.exception.response.status_code, 401)

    def test_response_signature_forgery_is_rejected(self):
        LocalHandler.tamper = "bad_signature"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_wrong_nonce_is_rejected(self):
        LocalHandler.tamper = "wrong_nonce"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_stale_attestation_is_rejected(self):
        LocalHandler.tamper = "stale"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_wrong_digest_is_rejected(self):
        LocalHandler.tamper = "wrong_digest"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_wrong_revision_is_rejected(self):
        LocalHandler.tamper = "wrong_revision"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_wrong_domain_is_rejected(self):
        LocalHandler.tamper = "wrong_domain"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_failed_stage_is_rejected(self):
        LocalHandler.tamper = "failed_stage"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_freshly_signed_invalid_counts_are_rejected(self):
        LocalHandler.tamper = "invalid_counts"
        with self.assertRaises(ValueError):
            client.check(self.bundle)

    def test_missing_secret_fails_before_network_request(self):
        with patch.dict(os.environ, {"SEANOVEL_ATTESTATION_SECRET": ""}):
            with patch.object(client.requests, "post") as network:
                with self.assertRaises(ValueError):
                    client.check(self.bundle)
                network.assert_not_called()

    def test_unauthorized_cron_get_is_rejected(self):
        response = requests.get(self.url, timeout=5)
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
