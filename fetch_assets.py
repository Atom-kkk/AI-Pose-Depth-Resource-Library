#!/usr/bin/env python3
"""把姿势库的缩略图（以及可选的原图）镜像到本地。

用法
    python3 fetch_assets.py            # 只下缩略图 thumbs/（约 12 MB，随仓库提交）
    python3 fetch_assets.py --all      # 连原图 img/ 一起下（约 144 MB，同样入库）
    python3 fetch_assets.py --check    # 只检查本地完整性，不下载

特性：16 并发、失败重试、断点续传（已存在且大于 1 KB 的文件跳过）。
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://ai-pose-depth-gallery.pages.dev/"
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data", "pose-depth-zh.json")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
WORKERS = 16


def fetch(rel):
    dest = os.path.join(ROOT, rel)
    if os.path.exists(dest) and os.path.getsize(dest) > 1024:
        return rel, "skip", os.path.getsize(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(BASE + rel, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as resp:
                body = resp.read()
            if len(body) < 512:
                raise ValueError("too small: %d" % len(body))
            tmp = dest + ".part"
            with open(tmp, "wb") as fh:
                fh.write(body)
            os.replace(tmp, dest)
            return rel, "ok", len(body)
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    return rel, "fail: %s" % last, 0


def main(argv):
    want_all = "--all" in argv
    check_only = "--check" in argv

    with open(DATA, encoding="utf-8") as fh:
        rows = json.load(fh)

    jobs = sorted({r["缩略图"] for r in rows})
    if want_all:
        jobs += sorted({r["原图"] for r in rows})

    if check_only:
        missing = [j for j in jobs
                   if not (os.path.exists(os.path.join(ROOT, j))
                           and os.path.getsize(os.path.join(ROOT, j)) > 1024)]
        print("jobs: %d   missing: %d" % (len(jobs), len(missing)))
        for m in missing[:20]:
            print("  MISSING", m)
        return 1 if missing else 0

    print("total jobs: %d  (thumbs%s)" % (len(jobs), " + originals" if want_all else ""),
          flush=True)
    done = fails = 0
    bytes_total = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(fetch, rel) for rel in jobs]
        for fut in as_completed(futures):
            rel, status, size = fut.result()
            done += 1
            bytes_total += size
            if status.startswith("fail"):
                fails += 1
                print("FAIL", rel, status, flush=True)
            if done % 100 == 0:
                el = time.time() - started
                print("%d/%d  %.1f MB  %.0fs" % (done, len(jobs), bytes_total / 1048576, el),
                      flush=True)

    print("DONE done=%d fails=%d total=%.1f MB in %.0fs"
          % (done, fails, bytes_total / 1048576, time.time() - started), flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
