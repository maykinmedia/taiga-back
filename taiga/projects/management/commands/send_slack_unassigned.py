
import datetime
from functools import reduce
from typing import List, NoReturn, Optional, Union, Any

from slack import WebClient
from django.conf import settings
from django.core.management.base import (BaseCommand, CommandError,
                                         CommandParser)
from django.db.models import Q, QuerySet
from django.utils import timezone

from taiga.projects.issues.models import Issue


class Command(BaseCommand):
    help = "Sends Slack notifications for recently-added issues that weren't assigned"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--last-updated",
            type=int,
            default=60,
            help="Send notifications for the issues created in the last x minutes. Default: 60."
        )
        parser.add_argument(
            "--blacklist",
            nargs="*",
            default=getattr(settings, "PROJECTS_NOTIFICATION_BLACKLIST", None),
            help="ids or slugs of the project(s) which shouldn't be taken into account when retrieving issues."
        )

    def send_message(self, message: str, channel: str):
        self.client.chat_postMessage(channel=settings.SLACK_CHANNEL,
                                     link_names=1,
                                     text=message)

    def get_issues(self, last_updated: int, blacklist: Optional[List[Union[str, int]]]) -> QuerySet:
        now = timezone.now()
        time_diff = now - datetime.timedelta(seconds=last_updated * 60)

        issues = Issue.objects.filter(
            created_date__gte=time_diff,
            assigned_to__isnull=True,
            status__is_closed=False
        )

        if blacklist is not None:
            issues = issues.exclude(project__id__in=blacklist).exclude(project__slug__in=blacklist)

        return issues

    def handle(self, *args: Any, **options: Any) -> str:
        self.client = WebClient(token=settings.SLACK_BOT_TOKEN)

        issues = self.get_issues(options["last_updated"], options["blacklist"])
        self.issues = issues

        if issues.exists():
            domain = settings.TAIGA_SITES_DOMAIN
            issues_str = "\n".join(f"#{issue.ref}: {issue.subject} ({issue.project.slug}) - https://{domain}/project/{issue.project.slug}/issue/{issue.ref}" for issue in issues)

            # Should use Django pluralization instead, but messages should be sent in English
            message = (
                f"Taiga info: the following issue{'s were' if issues.count() > 1 else ' was'} recently added but not assigned:\n"
            )
            message += issues_str
            self.stdout.write(f"The following issues were found:\n{issues_str}")

            self.send_message(message, settings.SLACK_CHANNEL)
            style = self.style.SUCCESS
            self.stdout.write(
                style(f"Message sent")
            )
        else:
            self.stdout.write("No corresponding issues found.")

        return "End of command."
