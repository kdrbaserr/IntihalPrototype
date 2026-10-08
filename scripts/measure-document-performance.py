"""Measure real API/queue/worker timings and sampled memory; no mocked services.

Run from the repository root while Docker Compose is running.
"""

import argparse
import csv
import json
import secrets
import statistics
import subprocess
import threading
import time
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

SAMPLER = """
import json, os, pathlib, select, sys, time
while True:
    rss = 0
    for process in pathlib.Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        try:
            command = (process / 'cmdline').read_bytes().split(b'\\0')
            if not command or not (b'python' in command[0] or b'celery' in command[0]
                                   or b'uvicorn' in command[0]):
                continue
            status = (process / 'status').read_text()
            rss += int(next(line.split()[1] for line in status.splitlines()
                            if line.startswith('VmRSS:'))) * 1024
        except (OSError, StopIteration, ValueError):
            continue
    memory = int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text())
    print(json.dumps({'time': time.time(), 'rss_bytes': rss,
                      'cgroup_bytes': memory}), flush=True)
    if select.select([sys.stdin], [], [], .1)[0]:
        break
"""

SOURCE_TEXT = (
    "Akademik bir metinde kullanılan düşüncenin kaynağı açıkça belirtilmelidir. "
    "Doğru atıf, okuyucunun bilginin kökenini izlemesini sağlar.\n\n"
    "Kaynakça kaydı; yazar, eser adı ve yayın bilgisini tutarlı biçimde sunar. "
    "Doğrudan alıntılar özgün ifadeyi korur ve uygun konum bilgisiyle gösterilir.\n\n"
)
SIZES = {"small": 10 * 1024, "medium": 100 * 1024, "large": 1024 * 1024}


class MemoryMonitor:
    def __init__(self, service):
        self.samples = []
        self.process = subprocess.Popen(
            ["docker", "compose", "exec", "-T", service, "python", "-u", "-c", SAMPLER],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        self.reader = threading.Thread(target=self.read, daemon=True)
        self.reader.start()

    def read(self):
        for line in self.process.stdout:
            self.samples.append(json.loads(line))

    def stop(self):
        self.process.stdin.close()
        self.process.wait(timeout=15)
        self.reader.join(timeout=5)
        if self.process.returncode != 0:
            raise RuntimeError("Memory sampler failed: " + self.process.stderr.read())

    def summarize(self, started, finished):
        samples = [s for s in self.samples if started <= s["time"] <= finished]
        baseline = next(s for s in reversed(self.samples) if s["time"] < started)
        if not samples:
            raise RuntimeError("No memory samples recorded")
        return {"sample_count": len(samples),
                "rss_baseline_mib": baseline["rss_bytes"] / 2**20,
                "rss_peak_mib": max(s["rss_bytes"] for s in samples) / 2**20,
                "cgroup_baseline_mib": baseline["cgroup_bytes"] / 2**20,
                "cgroup_peak_mib": max(s["cgroup_bytes"] for s in samples) / 2**20}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000/api/v1")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=360)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.repeats > 3:
        parser.error("repeats must be 1..3 (upload rate limit is 10 per hour)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(method, path, body=None, content_type="application/json"):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        headers = {"Content-Type": content_type, "X-CSRF-Protection": "1"}
        req = Request(args.api + path, data=body, headers=headers, method=method)
        with opener.open(req, timeout=60) as response:
            content = response.read()
            return json.loads(content) if content else None

    user = {"email": f"benchmark-{uuid4()}@example.test",
            "password": secrets.token_urlsafe(24), "display_name": "Performance Test"}
    request("POST", "/auth/register", user)
    request("POST", "/auth/login", {key: user[key] for key in ("email", "password")})
    report = {"measured_at": datetime.now().astimezone().isoformat(), "format": "TXT",
              "sample_interval_seconds": 0.1, "repeats": args.repeats,
              "git_revision": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], text=True).strip(),
              "method": "Live API + existing Celery worker; synthetic repeated sample-corpus text",
              "memory_method": "100ms samples: cgroup memory.current includes cache and sampler; "
                               "RSS sums Python/Celery/Uvicorn processes, excluding sampler",
              "runs": []}
    monitors = {service: MemoryMonitor(service) for service in ("api", "worker")}

    def save():
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        deadline = time.monotonic() + 15
        while not all(m.samples for m in monitors.values()):
            if time.monotonic() >= deadline:
                raise RuntimeError("Memory samplers did not start")
            time.sleep(0.1)
        for repeat in range(1, args.repeats + 1):
            for label, target in SIZES.items():
                unit = SOURCE_TEXT.encode()
                payload = unit * (target // len(unit)) + b"x" * (target % len(unit))
                boundary = "benchmark-" + uuid4().hex
                body = (f'--{boundary}\r\nContent-Disposition: form-data; name="retention_days"'
                        '\r\n\r\n7\r\n' +
                        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                        f'filename="benchmark-{label}-{repeat}.txt"\r\n'
                        'Content-Type: text/plain\r\n\r\n').encode() + payload + (
                            f"\r\n--{boundary}--\r\n").encode()
                started_at, started = time.time(), time.perf_counter()
                document = request("POST", "/documents", body,
                                   f"multipart/form-data; boundary={boundary}")
                uploaded = time.perf_counter()
                run = {"size": label, "repeat": repeat, "bytes": len(payload),
                       "words": len(payload.decode().split()), "document_id": document["id"],
                       "upload_seconds": uploaded - started}
                report["runs"].append(run)
                save()
                analysis = request("POST", f'/documents/{document["id"]}/analysis')
                run["analysis_id"] = analysis["id"]
                accepted = time.perf_counter()
                deadline = time.monotonic() + args.timeout
                while True:
                    state = request("GET", f'/documents/{document["id"]}')
                    if state["status"] in {"completed", "failed"}:
                        break
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"{label} analysis exceeded {args.timeout}s")
                    time.sleep(0.25)
                finished_at, finished = time.time(), time.perf_counter()
                metadata = request("GET", f'/analyses/{analysis["id"]}')
                run.update(status=state["status"], failure_reason=state["failure_reason"],
                           submit_seconds=accepted - uploaded,
                           queue_and_processing_seconds=finished - accepted,
                           upload_to_completion_seconds=finished - started)
                if metadata["started_at"] and metadata["completed_at"]:
                    run["analysis_seconds"] = (
                        datetime.fromisoformat(metadata["completed_at"]) -
                        datetime.fromisoformat(metadata["started_at"])).total_seconds()
                run["memory"] = {s: m.summarize(started_at, finished_at)
                                 for s, m in monitors.items()}
                report_start = time.perf_counter()
                if state["status"] == "completed":
                    matches = request("GET", f'/analyses/{analysis["id"]}/matches?limit=1')
                    run.update(report_seconds=time.perf_counter() - report_start,
                               matches=matches["total"])
                request("DELETE", f'/documents/{document["id"]}')
                try:
                    request("GET", f'/documents/{document["id"]}')
                except HTTPError as error:
                    if error.code != 404:
                        raise
                else:
                    raise AssertionError("Deleted benchmark document remains accessible")
                run["cleanup_verified"] = True
                save()
                print(f'{label} #{repeat}: {run["upload_to_completion_seconds"]:.3f}s, '
                      f'worker RSS peak {run["memory"]["worker"]["rss_peak_mib"]:.2f} MiB, '
                      f'{state["status"]}', flush=True)
        report["summary"] = []
        for size in SIZES:
            runs = [r for r in report["runs"] if r["size"] == size]
            report["summary"].append({
                "size": size, "bytes": runs[0]["bytes"], "runs": len(runs),
                "median_total_seconds": statistics.median(
                    r["upload_to_completion_seconds"] for r in runs),
                "completed_runs": sum(r["status"] == "completed" for r in runs),
                "failed_runs": sum(r["status"] == "failed" for r in runs),
                "median_analysis_seconds": statistics.median(
                    r["analysis_seconds"] for r in runs if "analysis_seconds" in r
                ) if any("analysis_seconds" in r for r in runs) else None,
                "max_worker_rss_mib": max(r["memory"]["worker"]["rss_peak_mib"] for r in runs),
                "max_api_rss_mib": max(r["memory"]["api"]["rss_peak_mib"] for r in runs),
                "max_worker_cgroup_mib": max(
                    r["memory"]["worker"]["cgroup_peak_mib"] for r in runs),
                "max_api_cgroup_mib": max(r["memory"]["api"]["cgroup_peak_mib"] for r in runs),
            })
        save()
        with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(report["summary"][0]))
            writer.writeheader()
            writer.writerows(report["summary"])
    finally:
        save()
        for monitor in monitors.values():
            monitor.stop()
        request("POST", "/auth/logout")


if __name__ == "__main__":
    main()
