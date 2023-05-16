from slack import WebClient
from slack.errors import SlackApiError
from django.conf import settings

from taiga.projects.issues.models import Issue
from django.core.management.base import (BaseCommand, CommandError)

from django.utils import timezone
from django.db.models import Q, QuerySet
from functools import reduce
import datetime
from typing import List, NoReturn, Optional, Union, Any

SEVERITY_CHOICES = ["wishlist", "minor", "normal", "important", "critical"]
PRIORITY_CHOICES = ["low", "normal", "high"]


class Command(BaseCommand):
    help = "Sends Slack notifications if a specific priority/severity is set on an issue."

    def get_issues(self, severity: str, priority: str, last_updated: int, blacklist: Optional[List[Union[str, int]]]) -> QuerySet:
        now = timezone.now()
        time_diff = now - datetime.timedelta(seconds=last_updated * 60)

        # OR filter with all severity/priority possibilities
        severity_filters = reduce(
            lambda q1, q2: q1 | q2,
            [Q(severity__name__icontains=severity) for severity in SEVERITY_CHOICES[SEVERITY_CHOICES.index(severity):]]
        )

        priority_filters = reduce(
            lambda q1, q2: q1 | q2,
            [Q(priority__name__icontains=priority) for priority in PRIORITY_CHOICES[PRIORITY_CHOICES.index(priority):]]
        )

        issues = Issue.objects.filter(
            severity_filters | priority_filters,
            created_date__gte=time_diff,
            status__is_closed=False
        )

        if blacklist is not None:
            issues = issues.exclude(project__id__in=blacklist).exclude(project__slug__in=blacklist)

        return issues

    def handle(self, *args: Any, **options: Any) -> str:
        slack_bot_token = settings.SLACK_BOT_TOKEN
        slack_client = WebClient(token=slack_bot_token)
        slack_channel = settings.SLACK_CHANNEL

        issues = self.get_issues(options["severity"], options["priority"],
                                 options["last_updated"], options["blacklist"])
        self.issues = issues

        for issue in issues:
            try:
                slack_client.chat_postMessage(
                    channel=slack_channel,
                    text=f"Taiga alert: the following issue{'s were' if issue.count() > 1 else ' was'} recently set to {options['severity']}/{options['priority']}"
                    f"{' or higher' if options['severity'] != 'critical' or options['priority'] != 'high' else ''}:\n"
                )
            except SlackApiError as e:
                self.stdout.write(f"Got an error: {e.response['error']}")
