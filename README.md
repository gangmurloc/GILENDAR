# gilendar

텔레그램에 자연어로 일정을 보내면(예: "수요일 6시 랩미팅, 목요일 금요일 15~17시 대학교 특강, 18시 저녁"),
Gemini API가 이를 파싱해서 등록 전 미리보기를 보여주고, 확인하면 구글 캘린더에 자동으로 등록해주는 개인용 봇입니다.
등록된 일정은 구글 캘린더 알림(팝업)과 텔레그램 메시지, 두 채널로 알림을 받습니다.

## 1. 사전 준비

### 1-1. 텔레그램 봇 만들기
1. 텔레그램에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 전송, 안내에 따라 이름 설정.
2. 발급받은 토큰을 `.env`의 `TELEGRAM_BOT_TOKEN`에 저장.
3. [@userinfobot](https://t.me/userinfobot)에게 아무 메시지나 보내서 본인 `id`(숫자)를 확인 → `.env`의 `TELEGRAM_OWNER_ID`에 저장.
   - 이 값이 있어야 봇이 본인 메시지만 처리하고, 다른 사람이 봇을 찾아 써도 내 캘린더에 함부로 일정을 등록하지 못합니다.

### 1-2. 구글 캘린더 API 사용 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 새 프로젝트 생성.
2. "API 및 서비스 > 라이브러리"에서 **Google Calendar API** 활성화.
3. "API 및 서비스 > OAuth 동의 화면": User Type은 `External`로 만들고, 테스트 사용자로 본인 구글 계정을 추가.
4. "API 및 서비스 > 사용자 인증 정보 > 사용자 인증 정보 만들기 > OAuth 클라이언트 ID" 선택, 애플리케이션 유형은 **데스크톱 앱**으로 생성.
5. 생성된 클라이언트의 JSON을 다운로드해서 프로젝트 루트에 `credentials.json`으로 저장.
   (이 파일은 `.gitignore`에 포함되어 있어 GitHub에 올라가지 않습니다.)

### 1-3. Gemini API 키 발급
1. [Google AI Studio](https://aistudio.google.com/apikey)에서 API 키 발급.
2. `.env`의 `GEMINI_API_KEY`에 저장.

## 2. 설치

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
copy .env.example .env       # Windows (mac/linux는 cp)
```

`.env` 파일을 열어 위에서 발급받은 값들을 채워 넣습니다.

## 3. 실행

```bash
python bot.py
```

최초 실행 시 브라우저가 열리며 구글 계정 로그인/동의를 요청합니다 (로컬 PC에서만 가능한 방식입니다).
동의가 끝나면 `data/token.json`에 인증 정보가 저장되어, 이후에는 재인증 없이 계속 동작합니다.

봇이 켜져 있는 동안에만 메시지를 받고 알림을 보낼 수 있으므로, 사용하는 동안 터미널을 계속 켜두세요.
(나중에 상시 서버/클라우드에 배포하면 24/7 동작하도록 확장할 수 있습니다.)

## 4. 사용법

텔레그램에서 봇에게 아무 문장이나 자연어로 일정을 보내면 됩니다.

```
수요일 6시 랩미팅, 목요일 금요일 15~17시 대학교 특강, 18시 저녁
```

봇이 해석한 일정 목록을 보여주면 "✅ 등록" 버튼을 눌러 확정합니다 (Gemini가 실수로 잘못 해석했을 경우 "❌ 취소"로 무시할 수 있습니다).

- `/today` : 오늘 일정 보기
- `/week` : 이번 주 일정 보기

등록된 일정은 구글 캘린더에서 시작 `CALENDAR_REMINDER_MINUTES`분 전 팝업 알림이 뜨고,
봇이 별도로 `TELEGRAM_REMINDER_MINUTES`분 전 텔레그램 메시지로도 알려줍니다 (둘 다 `.env`에서 조절 가능).

## 5. GitHub에 올릴 때 주의사항

`.gitignore`에 아래 항목이 이미 제외되어 있습니다. **절대 커밋하지 마세요.**
- `.env` (텔레그램/Gemini 키)
- `credentials.json` (구글 OAuth 클라이언트 시크릿)
- `data/` (구글 인증 토큰, 알림 발송 기록)

다른 PC나 클라우드에 배포할 때는 이 파일들을 별도로 안전하게 옮겨야 합니다.
