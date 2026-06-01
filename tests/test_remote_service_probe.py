import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.serving.health import probe_remote_services


class _ProbeHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append({"path": self.path, "payload": payload})
        if self.path == "/v1/chat/completions":
            response = {"choices": [{"message": {"content": "OK"}, "logprob": -0.1}]}
        elif self.path == "/score":
            response = {"score": 1.25}
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format, *args):
        return


class RemoteServiceProbeTests(unittest.TestCase):
    def setUp(self):
        _ProbeHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def test_probe_remote_services_posts_generator_and_verifier_requests(self):
        report = probe_remote_services(
            generator_endpoint=f"{self.base_url}/v1",
            generator_model="remote-generator",
            verifier_endpoint=f"{self.base_url}/score",
            timeout_seconds=5,
        )

        self.assertEqual(report["ok"], True)
        self.assertEqual(report["generator"]["candidate_count"], 1)
        self.assertEqual(report["generator"]["sample"], "OK")
        self.assertEqual(report["verifier"]["score"], 1.25)
        paths = [request["path"] for request in _ProbeHandler.requests]
        self.assertEqual(paths, ["/v1/chat/completions", "/score"])
        generator_payload = _ProbeHandler.requests[0]["payload"]
        self.assertEqual(generator_payload["model"], "remote-generator")

    def test_probe_remote_services_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "remote_service_probe.json"

            exit_code = main(
                [
                    "probe-remote-services",
                    "--generator-endpoint",
                    f"{self.base_url}/v1",
                    "--generator-model",
                    "remote-generator",
                    "--verifier-endpoint",
                    f"{self.base_url}/score",
                    "--output",
                    str(output_path),
                    "--timeout-seconds",
                    "5",
                ]
            )

            self.assertEqual(exit_code, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["ok"], True)
            self.assertEqual(report["generator"]["sample"], "OK")


if __name__ == "__main__":
    unittest.main()
