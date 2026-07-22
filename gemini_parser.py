from datetime import datetime

from google import genai
from google.genai import types

import config
from models import ParsedEventList

_client = genai.Client(api_key=config.GEMINI_API_KEY)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]

SYSTEM_INSTRUCTION = """너는 사용자의 한국어 자연어 일정 설명을 구조화된 캘린더 이벤트 목록으로 변환하는 어시스턴트다.

규칙:
- 오늘 날짜와 요일이 주어지면, "수요일" "목요일" 같은 표현은 항상 오늘 이후(오늘 포함) 가장 가까운 해당 요일로 계산한다.
- 한 문장에 여러 요일이 걸린 일정(예: "목요일 금요일 15~17시 특강")은 요일마다 별도 이벤트로 분리한다.
- 콤마(,)나 문맥상 구분되는 여러 일정이 한 메시지에 있으면 각각 별도 이벤트로 만든다.
- 시간이 명시되지 않고 앞뒤 문맥상 특정 요일들에 이어 붙는 항목(예: "..., 18시 저녁")은, 그 항목이 적용되는 것으로 보이는 모든 요일에 각각 이벤트를 만든다. 어느 요일에 적용되는지 애매하면 바로 직전에 언급된 요일에만 적용한다.
- 종료 시간이 없으면 end_time은 빈 문자열로 둔다.
- 시간은 24시간제 HH:MM, 날짜는 YYYY-MM-DD로 표기한다.
- all_day는 종일 일정(시간 언급이 전혀 없는 경우)일 때만 true로 한다.
- 이벤트 제목(title)은 사용자가 쓴 표현을 자연스럽게 다듬어서 짧게 쓴다.
"""


def parse_schedule_text(text: str, now: datetime) -> ParsedEventList:
    weekday = WEEKDAY_KR[now.weekday()]
    prompt = (
        f"오늘은 {now.strftime('%Y-%m-%d')} ({weekday}요일)이다.\n"
        f"다음 문장을 일정으로 변환해줘:\n{text}"
    )
    response = _client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=ParsedEventList,
            temperature=0.1,
        ),
    )
    return ParsedEventList.model_validate_json(response.text)
