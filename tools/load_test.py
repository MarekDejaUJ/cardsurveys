"""Simulated respondents for a load test of a Card Surveys installation.

Each simulated respondent opens the survey link, answers every screen (first
option of every question, cards in the order shown, the attention card last)
and finishes. Only the Python standard library is used.

    python tools/load_test.py http://127.0.0.1/cards SLUG --respondents 100 --concurrency 100
"""
from __future__ import annotations

import argparse
import html
import http.cookiejar
import json
import re
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

SCREEN = re.compile(r'name="screen" value="([^"]+)"')
CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


class Respondent:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.times: list[float] = []

    def request(self, url: str, data: dict | None = None) -> tuple[str, str]:
        body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
        # a browser sends the page address as the referrer within the site (policy same-origin),
        # which the CSRF check over HTTPS requires
        headers = {"Referer": url} if body is not None else {}
        t0 = time.perf_counter()
        with self.opener.open(urllib.request.Request(url, data=body, headers=headers), timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            final = resp.geturl()
        self.times.append(time.perf_counter() - t0)
        return final, text

    def answer(self, page: str) -> dict:
        data = {"screen": SCREEN.search(page).group(1), "client_ms": "2000"}
        m = CSRF.search(page)
        if m:
            data["csrf_token"] = m.group(1)
        if 'name="decision"' in page:
            data["decision"] = "agree"
        elif 'id="board"' in page:
            kind = re.search(r'data-kind="([a-z_]+)"', page).group(1)
            n = len(json.loads(html.unescape(re.search(r"data-elements='([^']*)'", page).group(1))))
            if kind in ("tier", "tier_aside"):
                p = {str(i): min(i, 1) for i in range(n)}
            elif kind == "arrow":
                p = {"arrows": [[0, 1]]}
            elif kind == "pile":
                p = {str(i): "p0" for i in range(n)}
            elif kind == "plane":
                p = {str(i): [10 * i + 10, 10 * i + 10] for i in range(n)}
            else:
                p = {f"{i},{j}": "apart" for i in range(n) for j in range(i + 1, n)}
            data["placements_json"] = json.dumps(p)
        elif re.search(r'name="pair_\d+_\d+"', page):
            for name in set(re.findall(r'name="(pair_\d+_\d+)"', page)):
                data[name] = "unrelated"
        elif 'id="sobTask"' in page or 'id="tapTask"' in page:
            cards = json.loads(html.unescape(re.search(r"data-cards='([^']*)'", page).group(1)))
            if 'id="sobTask"' in page:
                data["result_json"] = json.dumps({c["code"]: (i if i < len(cards) - 1 else "side") for i, c in enumerate(cards)})
            else:
                att = [c["code"] for c in cards if c.get("attention")]
                anchor = [c["code"] for c in cards if c.get("anchor")]
                normal = [c["code"] for c in cards if not c.get("attention") and not c.get("anchor")]
                first = 'data-attention="first"' in page
                if 'data-closes="1"' in page:
                    order = (att if first else []) + normal + ([] if first else att) + anchor
                else:
                    order = (att if first else []) + normal + anchor + ([] if first else att)
                data["result_json"] = json.dumps(order)
                gate = re.findall(r'name="gate" value="([^"]+)"', page)
                if gate:
                    data["gate"] = gate[0]
            data["events_json"] = "[]"
            data["block_ms"] = "3000"
        elif 'name="choice"' in page:
            data["choice"] = re.findall(r'name="choice" value="([^"]+)"', page)[0]
        else:
            names = set(re.findall(r'name="([A-Za-z][A-Za-z0-9_]*)"', page)) - {"csrf_token", "screen", "client_ms"}
            for name in names:
                sel = re.search(rf'<select id="q_{name}" name="{name}">(.*?)</select>', page, re.S)
                radio = re.findall(rf'name="{name}" value="([^"]+)"', page)
                if sel:
                    opts = re.findall(r'<option value="([^"]+)"', sel.group(1))
                    data[name] = opts[0] if opts else ""
                elif radio:
                    data[name] = radio[0]
                else:
                    data[name] = "1"
        return data

    def run(self, slug: str, max_screens: int = 300) -> int:
        url, page = self.request(f"{self.base}/s/{slug}")
        screens = 0
        while screens < max_screens:
            if "/done" in url or not SCREEN.search(page):
                return screens
            url, page = self.request(url.split("?")[0], self.answer(page))
            screens += 1
        raise RuntimeError("too many screens")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("base", help="base URL including the prefix, for example http://127.0.0.1/cards")
    ap.add_argument("slug", help="link code of an open survey")
    ap.add_argument("--respondents", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=100)
    args = ap.parse_args()
    results: list[tuple[bool, int, list[float], str]] = []
    lock = threading.Lock()
    sem = threading.Semaphore(args.concurrency)
    start_gate = threading.Event()

    def one():
        with sem:
            start_gate.wait()
            r = Respondent(args.base)
            try:
                n = r.run(args.slug)
                ok, err = True, ""
            except (urllib.error.URLError, RuntimeError, AttributeError, TimeoutError) as exc:
                n, ok, err = 0, False, repr(exc)[:200]
            with lock:
                results.append((ok, n, r.times, err))

    threads = [threading.Thread(target=one) for _ in range(args.respondents)]
    for t in threads:
        t.start()
    t0 = time.perf_counter()
    start_gate.set()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0
    times = [x for _, _, ts, _ in results for x in ts]
    ok = sum(1 for r in results if r[0])
    print(f"respondents: {len(results)}, completed: {ok}, failed: {len(results) - ok}")
    print(f"requests: {len(times)} in {wall:.1f} s ({len(times) / wall:.1f} per s)")
    if times:
        q = statistics.quantiles(times, n=100)
        print(f"latency: median {statistics.median(times) * 1000:.0f} ms, p95 {q[94] * 1000:.0f} ms, max {max(times) * 1000:.0f} ms")
    for _, _, _, err in results:
        if err:
            print("error:", err)
            break
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
