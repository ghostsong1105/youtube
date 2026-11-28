#!/usr/bin/env python3
"""키워드로 유튜브 새 영상을 검색해, 승인 대기용 '후보' GitHub 이슈를 만든다.

- YouTube Data API v3 search (호출 1회 = 100 유닛, 하루 기본 한도 10,000)
- 이미 자동 게시되는 채널은 후보에서 제외
- 이미 이슈로 만든 영상은 candidates.json 에 기록해 중복 방지
"""
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEYWORDS = ["연운", "동맹전", "연운 허수", "연운 DPS"]   # 검색어 (수정 가능)
LOOKBACK_DAYS = 30       # 업로드된 지 이 기간(일) 이내 영상만 후보로
MAX_RESULTS = 10         # 키워드당 최대 결과 수 (최대 50)

# RSS로 이미 자동 게시되는 채널은 후보에서 제외
EXCLUDE_CHANNEL_IDS = {
    "UCbxIxKqO3T_PkhZgFLsxVCg",
    "UCxgLmjOYux1dfiuC_2czDcw",
    "UCYlTdLiS-sQ0R-4RAJ0Icwg",
}

STATE_FILE = Path(__file__).with_name("candidates.json")
UA = "Mozilla/5.0 (yt-discord-notifier)"
API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
REVIEW_WEBHOOK = os.environ.get("DISCORD_REVIEW_WEBHOOK_URL", "")  # 선택: 비공개 알림 채널

LABELS = {"candidate": "fbca04", "approve": "0e8a16", "posted": "6f42c1"}


def request(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        # URL(키/토큰 포함 가능)은 로그에 남기지 않고 호스트만 표시
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


def ensure_labels():
    for name, color in LABELS.items():
        try:
            gh("POST", "/labels", {"name": name, "color": color})
        except RuntimeError:
            pass  # 이미 존재


def yt_search(keyword):
    after = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {"part": "snippet", "q": keyword, "type": "video", "order": "date",
              "maxResults": MAX_RESULTS, "publishedAfter": after,
              "key": API_KEY}
    data = request("https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params))
    results = []
    for it in data.get("items", []):
        sn = it["snippet"]
        results.append({
            "id": it["id"]["videoId"],
            "title": html.unescape(sn["title"]),
            "channel_id": sn["channelId"],
            "channel": html.unescape(sn["channelTitle"]),
            "published": sn["publishedAt"],
            "keyword": keyword,
        })
    return results


def load_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else []


def main():
    if not API_KEY:
        raise SystemExit("YOUTUBE_API_KEY 가 설정되지 않았습니다.")

    ensure_labels()
    seen_list = load_state()
    seen = set(seen_list)
    created = 0

    for kw in KEYWORDS:
        try:
            results = yt_search(kw)
        except Exception as e:
            print(f"[검색 실패: {kw}] {e}")
            continue

        for v in reversed(results):  # 오래된 것부터
            if v["id"] in seen or v["channel_id"] in EXCLUDE_CHANNEL_IDS:
                continue
            link = f"https://www.youtube.com/watch?v={v['id']}"
            body = (
                f"<!-- video:{v['id']} -->\n{link}\n\n"
                f"- 채널: {v['channel']}\n"
                f"- 업로드: {v['published']}\n"
                f"- 검색어: {v['keyword']}\n\n"
                "연운 관련 영상이 맞으면 `approve` 라벨을 붙이세요. 승인 채널에 바로 게시됩니다.\n"
                "아니면 이슈를 그냥 닫으면 됩니다. (다시 후보로 올라오지 않아요)\n"
            )
            try:
                issue = gh("POST", "/issues", {"title": f"[후보] {v['title']}"[:250],
                                                "body": body, "labels": ["candidate"]})
            except Exception as e:
                print(f"[이슈 생성 실패] {v['title']}: {e}")
                continue
            seen.add(v["id"])
            seen_list.append(v["id"])
            created += 1
            print(f"[후보] {v['title']} -> {issue['html_url']}")

            if REVIEW_WEBHOOK:
                try:
                    request(REVIEW_WEBHOOK,
                            data=json.dumps({"content": f"🔎 새 후보: {v['title']}\n{link}\n승인하러 가기: {issue['html_url']}"}).encode(),
                            headers={"Content-Type": "application/json"}, method="POST")
                except Exception as e:
                    print(f"[비공개 채널 알림 실패] {e}")

    STATE_FILE.write_text(json.dumps(seen_list[-2000:], indent=1))
    print(f"완료: 새 후보 {created}개")


if __name__ == "__main__":
    main()
