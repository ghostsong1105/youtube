#!/usr/bin/env python3
"""후보 이슈에 approve 라벨이 붙으면 승인 채널(텍스트/포럼 자동 판별)에 게시하고 이슈를 닫는다."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (yt-discord-notifier)"
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")


def request(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        host = urllib.parse.urlparse(url).netloc  # 웹훅 토큰이 로그/댓글에 남지 않게 호스트만
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


def main():
    n = os.environ["ISSUE_NUMBER"]

    issue = gh("GET", f"/issues/{n}")
    names = {l["name"] for l in issue.get("labels", [])}
    if "candidate" not in names:
        print("후보 이슈가 아니어서 건너뜀")
        return
    if "posted" in names:
        print("이미 게시된 이슈라 건너뜀")
        return

    m = re.search(r"<!-- video:([A-Za-z0-9_-]{11}) -->", issue.get("body") or "")
    if not m:
        print("영상 ID를 찾지 못함")
        return

    link = f"https://www.youtube.com/watch?v={m.group(1)}"
    title = re.sub(r"^\[후보\]\s*", "", issue["title"])
    webhook = os.environ.get("DISCORD_APPROVED_WEBHOOK_URL", "")
    if not webhook:
        gh("POST", f"/issues/{n}/comments", {"body": "❌ DISCORD_APPROVED_WEBHOOK_URL 시크릿이 설정되어 있지 않습니다."})
        raise SystemExit(1)

    headers = {"Content-Type": "application/json"}
    try:
        try:
            # 일반 텍스트 채널이면 이대로 전송됨
            request(webhook, data=json.dumps({"content": f"📺 새 영상\n{link}"}).encode(),
                    headers=headers, method="POST")
            kind = "텍스트"
        except RuntimeError as e:
            if "thread_name" not in str(e):
                raise
            # 포럼 채널이면 영상 제목으로 새 게시글(스레드) 생성
            request(webhook, data=json.dumps({"content": link, "thread_name": title[:100]}).encode(),
                    headers=headers, method="POST")
            kind = "포럼"
    except RuntimeError as e:
        gh("POST", f"/issues/{n}/comments", {"body": f"❌ 디스코드 전송 실패: {e}"})
        raise SystemExit(1)

    gh("POST", f"/issues/{n}/labels", {"labels": ["posted"]})
    gh("POST", f"/issues/{n}/comments",
       {"body": f"✅ {kind} 채널에 게시했습니다."})
    gh("PATCH", f"/issues/{n}", {"state": "closed", "state_reason": "completed"})
    print(f"게시 완료: {title}")


if __name__ == "__main__":
    main()
