from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db.models import Q
from django.utils import timezone

from taiga.projects.models import Project
from taiga.projects.userstories.models import UserStory


class Command(BaseCommand):
    help = (
        "Email every user a compact overview of the open user stories assigned to them on the "
        "Kanban board of a project, grouped by column and ranked by due date. "
        "User stories without a due date are ranked as if they are due today. To be run once per week."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--project",
            required=True,
            help="Slug of the project whose Kanban board is used.",
        )
        parser.add_argument(
            "--user",
            nargs="*",
            default=None,
            help="Only send the reminder to these users (username or email address).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report who would receive a reminder, without sending any email.",
        )

    def get_userstories_per_user(self, project: Project, users: Optional[Sequence[str]]) -> Dict:
        userstories = (
            UserStory.objects.filter(project=project, is_closed=False, status__is_archived=False)
            .select_related("status", "assigned_to")
            .prefetch_related("assigned_users")
        )

        userstories_per_user = defaultdict(list)
        for userstory in userstories:
            assignees = set(userstory.assigned_users.all())
            if userstory.assigned_to:
                assignees.add(userstory.assigned_to)

            for user in assignees:
                if not user.is_active:
                    continue
                if users and user.username not in users and user.email not in users:
                    continue
                userstories_per_user[user].append(userstory)

        return userstories_per_user

    def get_columns(self, project: Project, userstories: List[UserStory]) -> List[Dict[str, Any]]:
        """
        Group the user stories per Kanban column (left column first) and rank them by due date.
        """
        today = timezone.localdate()
        columns = []
        for status in project.us_statuses.filter(is_archived=False).order_by("order", "name"):
            column_userstories = sorted(
                (us for us in userstories if us.status_id == status.id),
                key=lambda us: (us.due_date or today, us.kanban_order),
            )
            if not column_userstories:
                continue

            columns.append({
                "status": status,
                "userstories": [
                    {
                        "userstory": us,
                        "due_date": us.due_date,
                        "is_overdue": us.due_date is not None and us.due_date < today,
                        "is_due_today": us.due_date == today,
                    }
                    for us in column_userstories
                ],
            })
        return columns

    def handle(self, *args: Any, **options: Any) -> None:
        from taiga.projects.notifications.services import _make_template_mail

        try:
            project = Project.objects.get(slug=options["project"])
        except Project.DoesNotExist:
            raise CommandError(f"Project with slug '{options['project']}' does not exist.")

        userstories_per_user = self.get_userstories_per_user(project, options["user"])
        if not userstories_per_user:
            self.stdout.write("No assigned open user stories found.")
            return

        email = _make_template_mail("userstories/userstories-weekly-reminder")
        today = timezone.localdate()

        for user, userstories in userstories_per_user.items():
            columns = self.get_columns(project, userstories)
            nr_userstories = sum(len(column["userstories"]) for column in columns)
            nr_overdue = sum(
                1 for column in columns for row in column["userstories"] if row["is_overdue"]
            )
            self.stdout.write(f"{user.email}: {nr_userstories} user stories ({nr_overdue} overdue)")

            if options["dry_run"]:
                continue

            context = {
                "user": user,
                "project": project,
                "columns": columns,
                "nr_userstories": nr_userstories,
                "nr_overdue": nr_overdue,
                "today": today,
                "lang": user.lang or settings.LANGUAGE_CODE,
            }
            email.send(user.email, context)

        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Sent {len(userstories_per_user)} reminder(s)."))
