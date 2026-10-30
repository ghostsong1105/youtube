#!/usr/bin/env python3
"""유튜브 채널 새 영상 -> 디스코드 웹훅 자동 링크 (외부 라이브러리 불필요)

사용법:
  1) 환경변수 DISCORD_WEBHOOK_URL 에 웹훅 주소 설정
  2) python yt_to_discord.py   (cron 등으로 5~10분마다 실행)

첫 실행 때는 기존 영상을 '이미 본 영상'으로만 기록하고 전송하지 않습니다.
(처음부터 최근 영상 15개씩 쏟아지는 것 방지)
"""
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

CHANNELS = {
    "fromage-e": "UCbxIxKqO3T_PkhZgFLsxVCg",
    "emfa1213": "UCxgLmjOYux1dfiuC_2czDcw",
}

STATE_FILE = Path(__file__).with_name("seen.json")
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
UA = "Mozilla/5.0 (yt-discord-notifier)"  # 디스코드는 기본 UA를 403 차단하는 경우가 있음

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}


def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def fetch_videos(channel_id):
    """최신순 [(video_id, title, link), ...] 반환"""
    root = ET.fromstring(http(FEED_URL.format(channel_id)))
    videos = []
    for e in root.findall("a:entry", NS):
        vid = e.find("yt:videoId", NS).text
        title = e.find("a:title", NS).text
        link = e.find("a:link", NS).attrib["href"]
        videos.append((vid, title, link))
    return videos


def send_discord(content):
    body = json.dumps({"content": content}).encode()
    http(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json"})


def main():
    if not WEBHOOK_URL:
        raise SystemExit("DISCORD_WEBHOOK_URL 환경변수를 설정하세요.")

    first_run = not STATE_FILE.exists()
    seen = set() if first_run else set(json.loads(STATE_FILE.read_text()))

    for name, cid in CHANNELS.items():
        try:
            videos = fetch_videos(cid)
        except Exception as e:
            print(f"[{name}] 피드 가져오기 실패: {e}")
            continue

        # 오래된 것부터 보내서 순서 유지
        for vid, title, link in reversed(videos):
            if vid in seen:
                continue
            seen.add(vid)
            if not first_run:
                try:
                    send_discord(f"📺 **{name}** 새 영상\n{link}")
                    print(f"[{name}] 전송: {title}")
                except Exception as e:
                    seen.discard(vid)  # 실패하면 다음 실행 때 재시도
                    print(f"[{name}] 전송 실패: {e}")

    STATE_FILE.write_text(json.dumps(sorted(seen)))


if __name__ == "__main__":
    main()
