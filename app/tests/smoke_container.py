"""Exercise the packaged app on a local running container, using synthetic demo data."""

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18080"
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, body=None, csrf=None):
    headers = {"Origin": base}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    content = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        content = json.dumps(body).encode()
    with client.open(
        urllib.request.Request(base + path, data=content, headers=headers), timeout=5
    ) as response:
        return response.read()


if __name__ == "__main__":
    for attempt in range(30):
        try:
            health = json.loads(request("/api/health"))
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 29:
                raise
            time.sleep(1)
    assert health["status"] == "ok"
    candidate = json.loads(request("/api/auth/demo", {"role": "candidate"}))
    assert candidate["role"] == "candidate"
    assert request("/api/candidate/profile.pdf").startswith(b"%PDF-")
    employer = json.loads(request("/api/auth/demo", {"role": "employer"}, candidate["csrf"]))
    assert employer["role"] == "employer"
    candidates = json.loads(request("/api/employer/candidates"))["candidates"]
    assert [item["id"] for item in candidates] == [candidate["id"]]
    schema = json.loads(request("/openapi.json"))
    assert (
        "application/pdf"
        in schema["paths"]["/api/candidate/resume/preview"]["post"]["requestBody"]["content"]
    )
    print("Container health, demo roles, font-backed PDF, scoped catalogue and OpenAPI passed")
