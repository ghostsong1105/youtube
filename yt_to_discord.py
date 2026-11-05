#!/usr/bin/env python3
"""유튜브 채널 새 영상 -> 디스코드 웹훅 자동 링크 (외부 라이브러리 불필요)

채널별로 보낼 웹훅(환경변수)과 방식을 지정합니다.
  mode="text"  : 일반 텍스트 채널에 메시지로 전송
  mode="forum" : 포럼 채널에 영상 제목으로 새 게시글(스레드) 생성

처음 보는 채널은 기존 영상을 '이미 본 영상'으로만 기록하고 전송하지 않습니다.
"""
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNELS = [
    {"name": "fromage-e", "id": "UCbxIxKqO3T_PkhZgFLsxVCg",
     "mode": "text", "webhook_env": "DISCORD_WEBHOOK_URL"},
    {"name": "emfa1213", "id": "UCxgLmjOYux1dfiuC_2czDcw",
     "mode": "text", "webhook_env": "DISCORD_WEBHOOK_URL"},
    # 포럼 채널용 (채널 이름은 원하는 대로 바꾸세요)
    {"name": "channel3", "id": "UCYlTdLiS-sQ0R-4RAJ0Icwg",
     "mode": "forum", "webhook_env": "DISCORD_FORUM_WEBHOOK_URL"},
]

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


def send_discord(webhook, mode, name, title, link):
    if mode == "forum":
        # 포럼 채널은 thread_name이 필수 (제목 최대 100자)
        payload = {"content": link, "thread_name": title[:100]}
    else:
        payload = {"content": f"📺 **{name}** 새 영상\n{link}"}
    http(webhook, data=json.dumps(payload).encode(),
         headers={"Content-Type": "application/json"})


def load_state():
    """{채널ID: [영상ID, ...]} 형태. 예전 형식(리스트)도 변환해서 읽음."""
    if not STATE_FILE.exists():
        return {}
    data = json.loads(STATE_FILE.read_text())
    if isinstance(data, list):  # 구버전: 텍스트 채널들에만 적용
        return {c["id"]: list(data) for c in CHANNELS if c["mode"] == "text"}
    return data


def main():
    state = load_state()

    for ch in CHANNELS:
        name, cid, mode = ch["name"], ch["id"], ch["mode"]
        webhook = os.environ.get(ch["webhook_env"], "")
        if not webhook:
            print(f"[{name}] {ch['webhook_env']} 미설정 - 건너뜀")
            continue

        first_run = cid not in state
        seen = set(state.get(cid, []))

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
            if first_run:
                continue
            try:
                send_discord(webhook, mode, name, title, link)
                print(f"[{name}] 전송: {title}")
            except Exception as e:
                seen.discard(vid)  # 실패하면 다음 실행 때 재시도
                print(f"[{name}] 전송 실패: {e}")

        state[cid] = sorted(seen)

    STATE_FILE.write_text(json.dumps(state, indent=1))


if __name__ == "__main__":
    main()
