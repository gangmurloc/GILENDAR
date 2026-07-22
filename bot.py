import logging
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import calendar_service
import config
import reminder_service
from gemini_parser import parse_schedule_text
from models import ParsedEventList

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _is_owner(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == config.TELEGRAM_OWNER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return
    await update.message.reply_text(
        "일정을 자연어로 보내주세요.\n"
        "예: 수요일 6시 랩미팅, 목요일 금요일 15~17시 대학교 특강, 18시 저녁\n\n"
        "/today - 오늘 일정 보기\n"
        "/week - 이번 주 일정 보기"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    tz = ZoneInfo(config.TIMEZONE)
    start_of_day = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(start_of_day, start_of_day + timedelta(days=1))
    await update.message.reply_text(_format_events(events, tz) or "오늘 일정이 없습니다.")


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    tz = ZoneInfo(config.TIMEZONE)
    start_of_day = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(start_of_day, start_of_day + timedelta(days=7))
    await update.message.reply_text(_format_events(events, tz) or "이번 주 일정이 없습니다.")


def _format_events(events: list[dict], tz: ZoneInfo) -> str:
    lines = []
    for ev in events:
        title = ev.get("summary", "(제목 없음)")
        date_time = ev["start"].get("dateTime")
        if date_time:
            dt = datetime.fromisoformat(date_time).astimezone(tz)
            label = f"{dt.month}/{dt.day}({WEEKDAY_KR[dt.weekday()]}) {dt.strftime('%H:%M')}"
        else:
            dt = datetime.strptime(ev["start"]["date"], "%Y-%m-%d")
            label = f"{dt.month}/{dt.day}({WEEKDAY_KR[dt.weekday()]}) 종일"
        lines.append(f"- {label} {title}")
    return "\n".join(lines)


def _format_preview(parsed: ParsedEventList) -> str:
    lines = ["다음 일정을 등록할까요?\n"]
    for ev in parsed.events:
        dt = datetime.strptime(ev.date, "%Y-%m-%d")
        weekday = WEEKDAY_KR[dt.weekday()]
        if ev.all_day:
            time_part = "종일"
        elif ev.end_time:
            time_part = f"{ev.start_time}~{ev.end_time}"
        else:
            time_part = ev.start_time
        lines.append(f"- {ev.date}({weekday}) {time_part} {ev.title}")
    return "\n".join(lines)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    try:
        parsed = parse_schedule_text(update.message.text, now)
    except Exception:
        logger.exception("Gemini parsing failed")
        await update.message.reply_text("일정을 이해하지 못했어요. 다시 표현해 주세요.")
        return

    if not parsed.events:
        await update.message.reply_text("일정을 찾지 못했어요. 다시 표현해 주세요.")
        return

    token = uuid.uuid4().hex[:8]
    context.chat_data.setdefault("pending", {})[token] = parsed
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ 등록", callback_data=f"confirm:{token}"),
                InlineKeyboardButton("❌ 취소", callback_data=f"cancel:{token}"),
            ]
        ]
    )
    await update.message.reply_text(_format_preview(parsed), reply_markup=keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return

    action, token = query.data.split(":", 1)
    pending = context.chat_data.get("pending", {})
    parsed = pending.pop(token, None)
    if parsed is None:
        await query.edit_message_text("이미 처리되었거나 만료된 요청입니다.")
        return

    if action == "cancel":
        await query.edit_message_text("취소되었습니다.")
        return

    created = []
    for ev in parsed.events:
        try:
            calendar_service.create_event(ev)
            created.append(ev)
        except Exception:
            logger.exception("Failed to create event: %s", ev)

    lines = [f"{len(created)}개 일정을 등록했습니다." if created else "등록에 실패했습니다."]
    for ev in created:
        lines.append(f"- {ev.date} {ev.start_time} {ev.title}")
    await query.edit_message_text("\n".join(lines))


def main():
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_repeating(reminder_service.check_reminders, interval=60, first=5)

    logger.info("봇을 시작합니다...")
    app.run_polling()


if __name__ == "__main__":
    main()
