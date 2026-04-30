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
from telegram.error import TelegramError

import database as db
from config import REMINDER_HOUR, REMINDER_DAYS_BEFORE_END
from utils.date_utils import next_month_str
from utils.error_handler import safe_send_message

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
    try:
        today = date.today()
        trigger_day = _third_last_day_of_month(today.year, today.month)

        if today.day != trigger_day:
            # Safety guard — scheduler fires daily at REMINDER_HOUR;
            # we only act on the right day.
            return

        try:
            next_month_num = (today.month % 12) + 1
            target = next_month_str()
            babies = db.get_birthdays_in_month(next_month_num)
        except Exception as e:
            logger.error(f"Failed to fetch birthdays for monthly reminder: {e}")
            return

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

        try:
            all_users = db.get_all_users()
        except Exception as e:
            logger.error(f"Failed to fetch users for monthly reminder: {e}")
            return
        
        sent = 0
        failed = 0
        
        for user in all_users:
            try:
                if user.get("telegram_id"):  # Only send to active users
                    success = await safe_send_message(
                        bot,
                        chat_id=user["telegram_id"],
                        text=message,
                        parse_mode="Markdown",
                    )
                    if success:
                        sent += 1
                    else:
                        failed += 1
            except Exception as e:
                logger.warning(f"Unexpected error messaging {user.get('name', 'unknown')}: {e}")
                failed += 1

        logger.info(
            "Monthly reminder sent to %d/%d users for %s. (%d failed)",
            sent,
            len(all_users),
            target,
            failed,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in send_monthly_reminder: {e}")


def setup_scheduler(app: Application) -> None:
    """Attach a BackgroundScheduler to the Application that fires the reminder daily."""
    global _scheduler
    
    try:
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
    except Exception as e:
        logger.exception(f"Unexpected error in setup_scheduler: {e}")
