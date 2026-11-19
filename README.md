# YouTube → Discord 알림 봇

GitHub Actions로 동작하는 유튜브 → 디스코드 알림 봇입니다.

## 기능

1. **채널 자동 알림** (10분마다) - 지정한 채널에 새 영상이 올라오면 디스코드로 자동 게시
   - 텍스트 채널 / 포럼 채널 둘 다 지원 (`yt_to_discord.py` 의 `CHANNELS`)
2. **키워드 후보 + 승인** (1시간마다) - 키워드(연운, 동맹전 등)로 검색한 영상을 GitHub 이슈로 올리고,
   `approve` 라벨을 붙이면 승인 채널에 게시 (`search_candidates.py`, `approve.py`)

## 파일 구조

```
yt_to_discord.py            채널 RSS 감시 -> 디스코드 (자동 게시)
search_candidates.py        키워드 검색 -> 후보 이슈 생성
approve.py                  approve 라벨 -> 승인 채널에 게시
.github/workflows/
  notify.yml                yt_to_discord.py 를 10분마다 실행
  search.yml                search_candidates.py 를 매시간 실행
  approve.yml               approve 라벨이 붙으면 approve.py 실행
```

`seen.json`, `candidates.json` 은 봇이 자동으로 만들고 커밋합니다 (이미 처리한 영상 기록). 지우지 마세요.

## 설정

### Secrets (Settings → Secrets and variables → Actions)

| 이름 | 용도 |
|---|---|
| `DISCORD_WEBHOOK_URL` | 채널 자동 알림 - 텍스트 채널 웹훅 |
| `DISCORD_FORUM_WEBHOOK_URL` | 채널 자동 알림 - 포럼 채널 웹훅 |
| `YOUTUBE_API_KEY` | 키워드 검색용 YouTube Data API v3 키 |
| `DISCORD_APPROVED_WEBHOOK_URL` | 승인된 영상을 올릴 채널 웹훅 (텍스트/포럼 자동 판별) |
| `DISCORD_REVIEW_WEBHOOK_URL` | (선택) 후보 알림을 받을 비공개 채널 웹훅 |

### 저장소 설정

- Settings → Actions → General → Workflow permissions → **Read and write permissions**
- Settings → General → Features → **Issues** 체크

### 사용

- 후보 이슈(`[후보] 제목`)를 확인해 맞으면 **`approve`** 라벨 → 자동 게시 후 이슈 닫힘
- 아니면 이슈를 그냥 닫기 (다시 후보로 올라오지 않음)

### 수정 포인트

- 감시 채널: `yt_to_discord.py` 의 `CHANNELS`
- 검색 키워드 / 기간 / 개수: `search_candidates.py` 위쪽 `KEYWORDS`, `LOOKBACK_DAYS`, `MAX_RESULTS`
