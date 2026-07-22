import html
import logging
import uuid
from datetime import date, datetime, timedelta
from datetime import time as dtime
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
import free_time
import reminder_service
from gemini_parser import handle_message
from models import EventUpdate, ParsedEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]
RECURRENCE_LABEL = {"daily": " (매일 반복)", "weekly": " (매주 반복)"}
CATEGORY_EMOJI = {"수업": "📘", "회의": "🧑‍🤝‍🧑", "약속": "🍽️", "기타": "📌"}


def _is_owner(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id == config.TELEGRAM_OWNER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return
    await update.message.reply_text(
        "일정을 자연어로 보내주세요.\n"
        "예: 수요일 6시 랩미팅, 목요일 금요일 15~17시 대학교 특강, 18시 저녁\n"
        "예: 매주 수요일 6시 랩미팅 (반복 일정)\n\n"
        "이미 등록된 일정도 자연어로 바꾸거나 지울 수 있어요.\n"
        "예: 목요일 랩미팅 취소해줘 / 수요일 랩미팅 7시로 옮겨줘\n\n"
        "일정/자유시간에 대해 그냥 물어봐도 됩니다.\n"
        "예: 이번 주 일정 알려줘 / 오늘 남는 시간에 뭐하면 좋을까?\n\n"
        "시간표나 포스터 사진을 보내도 읽어서 일정으로 등록할 수 있고, 음성 메시지로 말해도 됩니다.\n\n"
        f"매일 아침 {config.MORNING_DIGEST_HOUR}시에 오늘 일정을 먼저 알려드려요.\n\n"
        "/today - 오늘 일정 보기\n"
        "/week - 이번 주 일정 보기\n"
        "/free - 이번 주 자유시간 보기"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    tz = ZoneInfo(config.TIMEZONE)
    start_of_day = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(start_of_day, start_of_day + timedelta(days=1))
    await update.message.reply_text(
        _format_events(events, tz) or "오늘 일정이 없습니다.", parse_mode="HTML"
    )


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    tz = ZoneInfo(config.TIMEZONE)
    start_of_day = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(start_of_day, start_of_day + timedelta(days=7))
    await update.message.reply_text(
        _format_events(events, tz) or "이번 주 일정이 없습니다.", parse_mode="HTML"
    )


async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        return
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    slots = free_time.free_slots_for_range(now, days=7)
    await update.message.reply_text(_format_free_display(slots), parse_mode="HTML")


async def daily_digest(context: ContextTypes.DEFAULT_TYPE):
    tz = ZoneInfo(config.TIMEZONE)
    start_of_day = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(start_of_day, start_of_day + timedelta(days=1))
    slots = free_time.free_slots_for_range(start_of_day, days=1)
    lines = [
        "<b>☀️ 좋은 아침입니다! 오늘 일정</b>",
        _format_events(events, tz) or "오늘 일정이 없습니다.",
        "",
        "<b>🕳️ 오늘 자유시간</b>",
        _format_free_display(slots),
    ]
    await context.bot.send_message(
        chat_id=config.TELEGRAM_OWNER_ID, text="\n".join(lines), parse_mode="HTML"
    )


def _esc(text: str) -> str:
    return html.escape(text)


def _time_range(ev: dict, tz: ZoneInfo) -> str:
    start_dt = datetime.fromisoformat(ev["start"]["dateTime"]).astimezone(tz)
    end_raw = ev.get("end", {}).get("dateTime")
    if end_raw:
        end_dt = datetime.fromisoformat(end_raw).astimezone(tz)
        return f"{start_dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
    return start_dt.strftime("%H:%M")


def _describe_event_dict(ev: dict, tz: ZoneInfo) -> str:
    title = _esc(ev.get("summary", "(제목 없음)"))
    date_time = ev["start"].get("dateTime")
    if date_time:
        dt = datetime.fromisoformat(date_time).astimezone(tz)
        weekday = WEEKDAY_KR[dt.weekday()]
        return f"{dt.month}/{dt.day}({weekday}) {_time_range(ev, tz)} {title}"
    d = datetime.strptime(ev["start"]["date"], "%Y-%m-%d")
    weekday = WEEKDAY_KR[d.weekday()]
    return f"{d.month}/{d.day}({weekday}) 종일 {title}"


def _format_events(events: list[dict], tz: ZoneInfo) -> str:
    """날짜별로 묶어서 굵은 날짜 헤더 아래 시간순으로 보여준다."""
    day_lines: dict[date, list[str]] = {}
    order: list[date] = []
    for ev in events:
        title = _esc(ev.get("summary", "(제목 없음)"))
        date_time = ev["start"].get("dateTime")
        if date_time:
            dt = datetime.fromisoformat(date_time).astimezone(tz)
            day = dt.date()
            line = f"🕐 {_time_range(ev, tz)} {title}"
        else:
            day = datetime.strptime(ev["start"]["date"], "%Y-%m-%d").date()
            line = f"🗓️ 종일 {title}"
        if day not in day_lines:
            day_lines[day] = []
            order.append(day)
        day_lines[day].append(line)

    blocks = []
    for day in order:
        weekday = WEEKDAY_KR[day.weekday()]
        header = f"<b>{day.month}/{day.day}({weekday})</b>"
        blocks.append(header + "\n" + "\n".join(day_lines[day]))
    return "\n\n".join(blocks)


def _format_free_display(slots: list[tuple]) -> str:
    blocks = []
    for day, free_ranges in slots:
        weekday = WEEKDAY_KR[day.weekday()]
        header = f"<b>{day.month}/{day.day}({weekday})</b>"
        if not free_ranges:
            blocks.append(f"{header}\n자유시간 없음")
        else:
            body = "\n".join(f"🕐 {s.strftime('%H:%M')}~{e.strftime('%H:%M')}" for s, e in free_ranges)
            blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)


def _format_add_preview(events: list[ParsedEvent]) -> str:
    lines = ["<b>다음 일정을 등록할까요?</b>\n"]
    for ev in events:
        dt = datetime.strptime(ev.date, "%Y-%m-%d")
        weekday = WEEKDAY_KR[dt.weekday()]
        if ev.all_day:
            time_part = "종일"
        elif ev.end_time:
            time_part = f"{ev.start_time}~{ev.end_time}"
        else:
            time_part = ev.start_time
        recur_part = RECURRENCE_LABEL.get(ev.recurrence, "")
        reminder_part = f" ({ev.reminder_minutes}분 전 알림)" if ev.reminder_minutes else ""
        title = _esc(ev.title)
        emoji = CATEGORY_EMOJI.get(ev.category, "🕐")
        lines.append(f"{emoji} {ev.date}({weekday}) {time_part} {title}{recur_part}{reminder_part}")
        for other in calendar_service.find_overlaps(ev):
            other_title = _esc(other.get("summary", "(제목 없음)"))
            lines.append(f"  ⚠️ 기존 '{other_title}' 일정과 시간이 겹쳐요")
    return "\n".join(lines)


def _format_update_preview(updates: list[EventUpdate], tz: ZoneInfo) -> str:
    lines = ["<b>다음과 같이 변경할까요?</b>\n"]
    for u in updates:
        try:
            before = _describe_event_dict(calendar_service.get_event(u.event_id), tz)
        except Exception:
            logger.exception("Failed to fetch original event: %s", u.event_id)
            before = "(기존 일정 조회 실패)"
        dt = datetime.strptime(u.date, "%Y-%m-%d")
        weekday = WEEKDAY_KR[dt.weekday()]
        if u.all_day:
            time_part = "종일"
        elif u.end_time:
            time_part = f"{u.start_time}~{u.end_time}"
        else:
            time_part = u.start_time
        title = _esc(u.title)
        lines.append(f"🕐 {before}\n  → {u.date}({weekday}) {time_part} {title}")
    return "\n".join(lines)


def _format_delete_preview(delete_ids: list[str], tz: ZoneInfo) -> str:
    lines = ["<b>다음 일정을 삭제할까요?</b>\n"]
    for event_id in delete_ids:
        try:
            lines.append(f"🕐 {_describe_event_dict(calendar_service.get_event(event_id), tz)}")
        except Exception:
            logger.exception("Failed to fetch event to delete: %s", event_id)
            lines.append(f"🕐 (조회 실패: {event_id})")
    return "\n".join(lines)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    try:
        calendar_context = free_time.build_calendar_context(now)
        result = handle_message(now, calendar_context, text=update.message.text)
    except Exception:
        logger.exception("Gemini request failed")
        await update.message.reply_text("요청을 처리하지 못했어요. 다시 표현해 주세요.")
        return

    await _process_result(update, context, result, tz)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    try:
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = bytes(await photo_file.download_as_bytearray())
        calendar_context = free_time.build_calendar_context(now)
        result = handle_message(
            now,
            calendar_context,
            text=update.message.caption or "",
            media_bytes=image_bytes,
            media_mime_type="image/jpeg",
        )
    except Exception:
        logger.exception("Gemini image request failed")
        await update.message.reply_text("이미지를 처리하지 못했어요. 다시 시도해 주세요.")
        return

    await _process_result(update, context, result, tz)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_owner(update):
        await update.message.reply_text("이 봇은 개인용입니다.")
        return

    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    try:
        voice_file = await update.message.voice.get_file()
        audio_bytes = bytes(await voice_file.download_as_bytearray())
        calendar_context = free_time.build_calendar_context(now)
        result = handle_message(
            now,
            calendar_context,
            text="",
            media_bytes=audio_bytes,
            media_mime_type="audio/ogg",
        )
    except Exception:
        logger.exception("Gemini voice request failed")
        await update.message.reply_text("음성을 처리하지 못했어요. 다시 시도해 주세요.")
        return

    await _process_result(update, context, result, tz)


async def _process_result(update: Update, context: ContextTypes.DEFAULT_TYPE, result, tz: ZoneInfo):
    if result.action == "question":
        await update.message.reply_text(result.reply or "무슨 말인지 이해하지 못했어요.")
        return

    if result.action == "add":
        if not result.events:
            await update.message.reply_text("일정을 찾지 못했어요. 다시 표현해 주세요.")
            return
        preview = _format_add_preview(result.events)
        payload = {"action": "add", "events": result.events}
    elif result.action == "update":
        if not result.updates:
            await update.message.reply_text("변경할 일정을 찾지 못했어요. 다시 표현해 주세요.")
            return
        preview = _format_update_preview(result.updates, tz)
        payload = {"action": "update", "updates": result.updates}
    elif result.action == "delete":
        if not result.delete_ids:
            await update.message.reply_text("삭제할 일정을 찾지 못했어요. 다시 표현해 주세요.")
            return
        preview = _format_delete_preview(result.delete_ids, tz)
        payload = {"action": "delete", "delete_ids": result.delete_ids}
    else:
        await update.message.reply_text("무슨 말인지 이해하지 못했어요.")
        return

    token = uuid.uuid4().hex[:8]
    context.chat_data.setdefault("pending", {})[token] = payload
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ 확인", callback_data=f"confirm:{token}"),
                InlineKeyboardButton("❌ 취소", callback_data=f"cancel:{token}"),
            ]
        ]
    )
    await update.message.reply_text(preview, reply_markup=keyboard, parse_mode="HTML")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_owner(update):
        return

    button_action, token = query.data.split(":", 1)
    pending = context.chat_data.get("pending", {})
    payload = pending.pop(token, None)
    if payload is None:
        await query.edit_message_text("이미 처리되었거나 만료된 요청입니다.")
        return

    if button_action == "cancel":
        await query.edit_message_text("취소되었습니다.")
        return

    action = payload["action"]
    if action == "add":
        created = []
        for ev in payload["events"]:
            try:
                created_event = calendar_service.create_event(ev)
                created.append((ev, created_event))
            except Exception:
                logger.exception("Failed to create event: %s", ev)
        lines = [f"<b>{len(created)}개 일정을 등록했습니다.</b>" if created else "등록에 실패했습니다."]
        for ev, created_event in created:
            title = _esc(ev.title)
            emoji = CATEGORY_EMOJI.get(ev.category, "🕐")
            link = created_event.get("htmlLink")
            if link:
                lines.append(f"{emoji} {ev.date} {ev.start_time} <a href=\"{link}\">{title}</a>")
            else:
                lines.append(f"{emoji} {ev.date} {ev.start_time} {title}")
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
    elif action == "update":
        updated = 0
        for u in payload["updates"]:
            try:
                calendar_service.update_event(u)
                updated += 1
            except Exception:
                logger.exception("Failed to update event: %s", u)
        await query.edit_message_text(f"{updated}개 일정을 변경했습니다." if updated else "변경에 실패했습니다.")
    elif action == "delete":
        deleted_bodies = []
        for event_id in payload["delete_ids"]:
            try:
                original = calendar_service.get_event(event_id)
                calendar_service.delete_event(event_id)
                deleted_bodies.append(original)
            except Exception:
                logger.exception("Failed to delete event: %s", event_id)

        if not deleted_bodies:
            await query.edit_message_text("삭제에 실패했습니다.")
            return

        restore_token = uuid.uuid4().hex[:8]
        context.chat_data.setdefault("pending", {})[restore_token] = {
            "action": "restore",
            "events": deleted_bodies,
        }
        restore_keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("↩️ 되돌리기", callback_data=f"confirm:{restore_token}")]]
        )
        await query.edit_message_text(f"{len(deleted_bodies)}개 일정을 삭제했습니다.", reply_markup=restore_keyboard)
    elif action == "restore":
        restored = 0
        for original in payload["events"]:
            try:
                calendar_service.restore_event(original)
                restored += 1
            except Exception:
                logger.exception("Failed to restore event: %s", original)
        await query.edit_message_text(f"{restored}개 일정을 복구했습니다." if restored else "복구에 실패했습니다.")


def main():
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("free", free))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.job_queue.run_repeating(reminder_service.check_reminders, interval=60, first=5)
    app.job_queue.run_daily(
        daily_digest,
        time=dtime(hour=config.MORNING_DIGEST_HOUR, minute=0, tzinfo=ZoneInfo(config.TIMEZONE)),
    )

    logger.info("봇을 시작합니다...")
    app.run_polling()


if __name__ == "__main__":
    main()
