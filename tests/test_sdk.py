from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest
from urllib.parse import parse_qs

from peru_sdk._http import HTTPTransport, MAX_RESPONSE_BYTES
from peru_sdk.errors import SDKError
from peru_sdk.reniec import Identity, IdentityQuery, MockIdentityService
from peru_sdk.sunat import OAuth2TokenProvider, StaticToken, ValidityClient, ValidityQuery, parse_validity_response

CASES = json.loads((Path(__file__).resolve().parent / "data/conformance.json").read_text(encoding="utf-8"))
ACCEPTED = b'{"success":true,"data":{"estadoCp":1,"estadoRuc":"00","condDomiRuc":"00"}}'


class Server:
    def __init__(self, callback):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                # Consume the request before replying so close cannot reset an unread body.
                self.request_body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                callback(self)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def respond(handler, body=ACCEPTED, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class SharedConformance(unittest.TestCase):
    def test_queries(self):
        for case in CASES["query_cases"]:
            with self.subTest(case=case["id"]):
                data = {**CASES["query"], **case["patch"]}
                if case["valid"]:
                    ValidityQuery(**data)
                else:
                    with self.assertRaises(ValueError):
                        ValidityQuery(**data)

    def test_responses(self):
        for case in CASES["response_cases"]:
            with self.subTest(case=case["id"]):
                body = case["raw_body"].encode() if "raw_body" in case else json.dumps(case["body"]).encode()
                if "error" in case:
                    with self.assertRaises(SDKError) as caught:
                        parse_validity_response(body)
                    self.assertEqual(caught.exception.kind, case["error"])
                else:
                    result = json.loads(json.dumps(asdict(parse_validity_response(body))))
                    self.assertEqual(result, case["expected"])

    def test_synthetic_identities(self):
        records = [Identity(**r) for r in CASES["identity_records"]]
        service = MockIdentityService(records)
        for case in CASES["identity_cases"]:
            with self.subTest(case=case["id"]):
                if case.get("invalid"):
                    with self.assertRaises(ValueError):
                        IdentityQuery(case["dni"])
                elif case["found"]:
                    self.assertEqual(service.lookup(IdentityQuery(case["dni"])), records[0])
                else:
                    with self.assertRaises(SDKError) as caught:
                        service.lookup(IdentityQuery(case["dni"]))
                    self.assertEqual(caught.exception.kind, "not_found")
        with self.assertRaises(ValueError):
            MockIdentityService(records + records)


class HTTPTests(unittest.TestCase):
    def test_exchange_precision_and_expiry(self):
        requests = []

        def handle(handler):
            body = handler.request_body
            requests.append((handler.path, dict(handler.headers), body))
            if handler.path == "/token":
                respond(handler, b'{"access_token":"synthetic-token","token_type":"Bearer","expires_in":100}')
            else:
                respond(handler)

        with Server(handle) as server:
            tokens = OAuth2TokenProvider("synthetic-client", "synthetic-secret", token_url=server.url + "/token")
            clock = [1000.0]
            tokens._clock = lambda: clock[0]
            client = ValidityClient("20000000002", tokens, base_url=server.url)
            for _ in range(2):
                self.assertEqual(client.check(ValidityQuery(**CASES["query"])).document_status, "1")
            self.assertEqual(sum(path == "/token" for path, _, _ in requests), 1)
            clock[0] += 91
            client.check(ValidityQuery(**CASES["query"]))
            self.assertEqual(sum(path == "/token" for path, _, _ in requests), 2)

        for path, headers, body in requests:
            if path == "/token":
                form = parse_qs(body.decode())
                self.assertEqual(form["grant_type"], ["client_credentials"])
                self.assertEqual(form["scope"], ["https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"])
                self.assertEqual(form["client_id"], ["synthetic-client"])
                self.assertEqual(form["client_secret"], ["synthetic-secret"])
            else:
                self.assertEqual(path, "/v1/contribuyente/contribuyentes/20000000002/validarcomprobante")
                self.assertEqual(headers["Authorization"], "Bearer synthetic-token")
                payload = json.loads(body, parse_float=Decimal)
                self.assertEqual(payload["numRuc"], "20000000001")
                self.assertEqual(payload["fechaEmision"], "02/11/2026")
                self.assertEqual(payload["monto"], Decimal("123456789012345.67"))
                self.assertEqual(payload["numero"], 123)

    def test_concurrent_token_refresh(self):
        requests = []

        def handle(handler):
            requests.append(handler.path)
            respond(handler, b'{"access_token":"synthetic-token","token_type":"Bearer","expires_in":100}')

        with Server(handle) as server:
            provider = OAuth2TokenProvider("id", "secret", token_url=server.url)
            with ThreadPoolExecutor(max_workers=10) as executor:
                self.assertEqual(list(executor.map(lambda _: provider.token(), range(10))), ["synthetic-token"] * 10)
        self.assertEqual(len(requests), 1)

    def test_statuses_no_redirect_or_retry(self):
        for status in (302, 401, 403, 429, 500):
            with self.subTest(status=status):
                requests = []

                def handle(handler):
                    requests.append(handler.path)
                    handler.send_response(status)
                    handler.send_header("Location", "http://127.0.0.1:1/leak")
                    handler.end_headers()
                    handler.wfile.write(b"synthetic-secret")

                with Server(handle) as server:
                    client = ValidityClient("20000000002", StaticToken("token"), base_url=server.url)
                    with self.assertRaises(SDKError) as caught:
                        client.check(ValidityQuery(**CASES["query"]))
                self.assertEqual(caught.exception.status, status)
                self.assertNotIn("synthetic-secret", str(caught.exception))
                self.assertEqual(len(requests), 1)

    def test_response_limit(self):
        with Server(lambda h: respond(h, b"x" * (MAX_RESPONSE_BYTES + 1))) as server:
            client = ValidityClient("20000000002", StaticToken("token"), base_url=server.url)
            with self.assertRaises(SDKError) as caught:
                client.check(ValidityQuery(**CASES["query"]))
            self.assertEqual(caught.exception.kind, "protocol")

    def test_invalid_endpoints_and_safe_repr(self):
        for endpoint in ("http://example.com", "https://user:password@example.com", "https://example.com?token=secret"):
            with self.assertRaises(SDKError):
                ValidityClient("20000000002", StaticToken("token"), base_url=endpoint)
        self.assertNotIn("do-not-log", repr(StaticToken("do-not-log")))
        self.assertNotIn("do-not-log", repr(OAuth2TokenProvider("id", "do-not-log")))
        with self.assertRaises(SDKError):
            StaticToken("header\ninjection")

    def test_malformed_token_responses(self):
        for body in ({}, None, {"access_token": "x", "token_type": "Bearer", "expires_in": 0},
                     {"access_token": "x", "token_type": "Bearer", "expires_in": True},
                     {"access_token": "x", "token_type": "Other", "expires_in": 10}):
            with self.subTest(body=body):
                with Server(lambda h: respond(h, json.dumps(body).encode())) as server:
                    provider = OAuth2TokenProvider("id", "secret", token_url=server.url)
                    with self.assertRaises(SDKError) as caught:
                        provider.token()
                    self.assertEqual(caught.exception.kind, "protocol")

    def test_validation_precedes_token_or_network(self):
        class UnexpectedToken:
            def token(self):
                raise AssertionError("token requested before validation")

        query = ValidityQuery(**CASES["query"])
        object.__setattr__(query, "amount", "1e2")
        client = ValidityClient("20000000002", UnexpectedToken())
        with self.assertRaises(ValueError):
            client.check(query)

    def test_invalid_timeout(self):
        self.assertRaises(SDKError, HTTPTransport, 0)


if __name__ == "__main__":
    unittest.main()
