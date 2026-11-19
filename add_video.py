#!/usr/bin/env python3
"""검색에 안 잡히는 영상을 URL로 직접 후보 이슈에 등록한다. (이후 approve 라벨로 게시)"""
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STATE_FILE = Path(__file__).with_name("candidates.json")
UA = "Mozilla/5.0 (yt-discord-notifier)"
API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
REVIEW_WEBHOOK = os.environ.get("DISCORD_REVIEW_WEBHOOK_URL", "")
LABELS = {"candidate": "fbca04", "approve": "0e8a16", "posted": "6f42c1"}


def request(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        host = urllib.parse.urlparse(url).netloc
        raise RuntimeError(f"HTTP {e.code} ({host}): {e.read().decode(errors='replace')[:300]}")


def gh(method, path, payload=None):
    return request(
        f"https://api.github.com/repos/{REPO}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {GH_TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "Content-Type": "application/json"},
    )


def parse_video_id(text):
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text.strip()):
        return text.strip()
    return None


def main():
    urls = [u for u in re.split(r"[\s,]+", os.environ.get("VIDEO_URL", "")) if u]
    if not urls:
        raise SystemExit("VIDEO_URL 이 비어 있습니다.")
    if not API_KEY:
        raise SystemExit("YOUTUBE_API_KEY 가 설정되지 않았습니다.")

    for name, color in LABELS.items():
        try:
            gh("POST", "/labels", {"name": name, "color": color})
        except RuntimeError:
            pass

    seen_list = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else []
    seen = set(seen_list)

    for u in urls:
        vid = parse_video_id(u)
        if not vid:
            print(f"[건너뜀] 영상 ID를 찾지 못함: {u}")
            continue
        if vid in seen:
            print(f"[건너뜀] 이미 후보로 등록된 영상: {vid}")
            continue

        params = {"part": "snippet", "id": vid, "key": API_KEY}
        data = request("https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(params))
        items = data.get("items", [])
        if not items:
            print(f"[건너뜀] 영상을 찾을 수 없음(비공개/삭제?): {vid}")
            continue
        sn = items[0]["snippet"]
        title = html.unescape(sn["title"])
        link = f"https://www.youtube.com/watch?v={vid}"
        body = (
            f"<!-- video:{vid} -->\n{link}\n\n"
            f"- 채널: {html.unescape(sn['channelTitle'])}\n"
            f"- 업로드: {sn['publishedAt']}\n"
            f"- 등록: 수동\n\n"
            "연운 관련 영상이 맞으면 `approve` 라벨을 붙이세요. 승인 채널에 바로 게시됩니다.\n"
            "아니면 이슈를 그냥 닫으면 됩니다.\n"
        )
        issue = gh("POST", "/issues", {"title": f"[후보] {title}"[:250], "body": body, "labels": ["candidate"]})
        seen.add(vid)
        seen_list.append(vid)
        print(f"[등록] {title} -> {issue['html_url']}")

        if REVIEW_WEBHOOK:
            try:
                request(REVIEW_WEBHOOK,
                        data=json.dumps({"content": f"🔎 수동 등록: {title}\n{link}\n승인하러 가기: {issue['html_url']}"}).encode(),
                        headers={"Content-Type": "application/json"}, method="POST")
            except Exception as e:
                print(f"[비공개 채널 알림 실패] {e}")

    STATE_FILE.write_text(json.dumps(seen_list[-2000:], indent=1))


if __name__ == "__main__":
    main()
