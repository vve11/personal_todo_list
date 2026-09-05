"""Optional manual trigger: python3 -m app.jobs.reminder_job"""

from app import create_app
from app.services.reminder_service import ReminderService


def main() -> None:
    app = create_app()
    with app.app_context():
        result = ReminderService().run_scheduled_reminders()
        print(
            "Reminder job finished: "
            f"sent={result['sent']} skipped={result['skipped']} failed={result['failed']}"
        )


if __name__ == "__main__":
    main()
