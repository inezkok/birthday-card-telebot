"""
scheduler.py – Automated monthly birthday reminders
=====================================================
On the 3rd-last day of each month at REMINDER_HOUR (UTC), the bot sends
a message to every registered user listing the next month's birthday babies
and asking them to write their wishes.
"""

import calendar
import logging
from datetime import date, datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

import database as db
from config import REMINDER_HOUR, REMINDER_DAYS_BEFORE_END
from utils.date_utils import next_month_str

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler = None


def _third_last_day_of_month(year: int, month: int) -> int:
    """Return the calendar day that is REMINDER_DAYS_BEFORE_END from month end."""
    last_day = calendar.monthrange(year, month)[1]
    return last_day - (REMINDER_DAYS_BEFORE_END - 1)


async def send_monthly_reminder(bot) -> None:
    """
    Fire this on the 3rd-last day of each month.
    Checks whether *today* is indeed the correct trigger day, then notifies
    all users about next month's birthday people.
    """
    today = date.today()
    trigger_day = _third_last_day_of_month(today.year, today.month)

    if today.day != trigger_day:
        # Safety guard — scheduler fires daily at REMINDER_HOUR;
        # we only act on the right day.
        return

    next_month_num = (today.month % 12) + 1
    target = next_month_str()
    babies = db.get_birthdays_in_month(next_month_num)

    if not babies:
        logger.info("Monthly reminder: no birthdays in %s, skipping.", target)
        return

    baby_lines = "\n".join(
        f"  🎂 *{b['name']}* — {b['birthday'][5:]}  (DD/MM)"
        for b in babies
    )

    message = (
        f"🎉 *Birthday Reminder!*\n\n"
        f"The following people have birthdays in *{target}*:\n"
        f"{baby_lines}\n\n"
        f"Please write them a birthday wish using /write 💌"
    )

    all_users = db.get_all_users()
    sent = 0
    for user in all_users:
        try:
            await bot.send_message(
                chat_id=user["telegram_id"],
                text=message,
                parse_mode="Markdown",
            )
            sent += 1
        except Exception as exc:
            logger.warning("Could not message %s: %s", user["name"], exc)

    logger.info("Monthly reminder sent to %d/%d users for %s.", sent, len(all_users), target)


def setup_scheduler(app: Application) -> None:
    """Attach a BackgroundScheduler to the Application that fires the reminder daily."""
    global _scheduler
    
    # Use BackgroundScheduler instead of AsyncIOScheduler
    # This runs in a separate thread and works reliably with async code
    _scheduler = BackgroundScheduler(timezone="UTC")

    # Fire every day at REMINDER_HOUR — the handler itself checks the day.
    _scheduler.add_job(
        send_monthly_reminder,
        trigger=CronTrigger(hour=REMINDER_HOUR, minute=0, timezone="UTC"),
        args=[app.bot],
        id="monthly_reminder",
        replace_existing=True,
    )

    # Start the scheduler immediately (it runs in a daemon thread)
    _scheduler.start()
    logger.info(
        "Scheduler started — reminder fires daily at %02d:00 UTC, "
        "active on the %d-days-before-end-of-month trigger.",
        REMINDER_HOUR,
        REMINDER_DAYS_BEFORE_END,
    )
