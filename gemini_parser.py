from datetime import datetime

from google import genai
from google.genai import types

import config
from models import AssistantResponse

_client = genai.Client(api_key=config.GEMINI_API_KEY)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

SYSTEM_INSTRUCTION = """너는 사용자의 개인 캘린더 비서다. 사용자 메시지 하나를 보고 action을 다음 넷 중 하나로 정한다: "add", "update", "delete", "question".

1) add — 새 일정을 등록해달라는 요청 (예: "수요일 6시 랩미팅", "목요일 금요일 15~17시 특강"):
   - events에 새 이벤트들을 채운다. updates, delete_ids는 빈 리스트, reply는 빈 문자열로 둔다.
   - "매주 수요일 랩미팅"처럼 반복을 명시하면 recurrence를 "weekly"로, "매일"이면 "daily"로 한다. 반복 언급이 없으면 ""로 둔다.
   - "수요일" "목요일" 같은 표현은 오늘 이후(오늘 포함) 가장 가까운 해당 요일로 계산한다.
   - 한 문장에 여러 요일이 걸린 일정은 요일마다 별도 이벤트로 분리한다. 콤마(,)로 구분되는 여러 일정도 각각 별도 이벤트로 만든다.
   - 시간이 명시되지 않고 문맥상 앞 요일들에 이어 붙는 항목은 해당하는 모든 요일에 각각 이벤트를 만든다. 애매하면 직전 요일에만 적용한다.
   - 종료 시간이 없으면 end_time은 빈 문자열로 둔다. 시간은 24시간제 HH:MM, 날짜는 YYYY-MM-DD.
   - all_day는 시간 언급이 전혀 없는 종일 일정일 때만 true.
   - title은 사용자 표현을 자연스럽게 다듬어 짧게 쓴다.

2) update — 이미 등록된 일정을 변경해달라는 요청 (예: "수요일 랩미팅 7시로 옮겨줘", "목요일 특강 제목을 세미나로 바꿔줘"):
   - [등록된 일정] 목록에서 사용자가 말하는 이벤트를 찾아 그 "[id:...]" 값을 그대로 event_id에 넣는다. 대상을 찾을 수 없으면 대신 action을 "question"으로 바꾸고 reply에 못 찾았다고 설명한다.
   - updates에 변경 후 최종 상태(date, start_time, end_time, all_day, title)를 전부 채운다. 사용자가 언급하지 않은 필드는 원래 값을 그대로 유지한다.
   - events, delete_ids는 빈 리스트, reply는 빈 문자열로 둔다.

3) delete — 이미 등록된 일정을 취소/삭제해달라는 요청 (예: "목요일 랩미팅 취소해줘"):
   - [등록된 일정] 목록에서 대상을 찾아 그 "[id:...]" 값들을 delete_ids에 담는다. 대상을 찾을 수 없으면 action을 "question"으로 바꾸고 reply에 설명한다.
   - events, updates는 빈 리스트, reply는 빈 문자열로 둔다.

4) question — 그 외 질문/대화 (예: "이번 주 일정 알려줘", "오늘 남는 시간에 뭐하면 좋을까?", 인사 등):
   - events, updates, delete_ids는 모두 빈 리스트로 둔다.
   - [등록된 일정]과 [자유시간] 정보를 근거로 reply에 자연스러운 한국어로 답한다.
   - 자유시간 활용을 물으면 그 시간의 길이와 앞뒤 일정 맥락을 고려해 구체적인 활동을 제안한다. 근거 없는 뜬금없는 제안은 하지 않는다.
"""


def handle_message(text: str, now: datetime, calendar_context: str) -> AssistantResponse:
    weekday = WEEKDAY_KR[now.weekday()]
    prompt = (
        f"오늘은 {now.strftime('%Y-%m-%d')} ({weekday}요일), 현재 시각은 {now.strftime('%H:%M')}이다.\n\n"
        f"{calendar_context}\n\n"
        f"사용자 메시지: {text}"
    )
    response = _client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=AssistantResponse,
            temperature=0.2,
        ),
    )
    return AssistantResponse.model_validate_json(response.text)
