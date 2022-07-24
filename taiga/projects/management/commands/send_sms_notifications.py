
import datetime
from functools import reduce
from typing import List, NoReturn, Optional, Union, Any

import messagebird
from django.conf import settings
from django.core.management.base import (BaseCommand, CommandError,
                                         CommandParser)
from django.db.models import Q, QuerySet
from django.utils import timezone
from messagebird.message import Message

from taiga.projects.issues.models import Issue

SEVERITY_CHOICES = ["wishlist", "minor", "normal", "important", "critical"]
PRIORITY_CHOICES = ["low", "normal", "high"]


class Command(BaseCommand):
    help = "Sends SMS notifications if a specific priority/severity is set on an issue."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--last-updated",
            type=int,
            default=5,
            help="Send notifications for the issues updated in the last x minutes. Default: 5."
        )
        parser.add_argument(
            "--severity",
            choices=SEVERITY_CHOICES,
            default="critical",
            help=(
                "Select issues matching the provided severity, or higher. "
                "If 'important' is selected, all issues with severity 'important' or 'critical' "
                "will be selected (using icontains on the name). Default: 'critical'."
            )
        )
        parser.add_argument(
            "--priority",
            choices=PRIORITY_CHOICES,
            default="high",
            help=(
                "Select issues matching the provided priority, or higher. "
                "If 'normal' is selected, all issues with severity 'normal' or 'high' "
                "will be selected (using icontains on the name). Default: 'high'."
            )
        )
        parser.add_argument(
            "--phonenumbers",
            nargs="*",
            default=getattr(settings, "MESSAGEBIRD_PHONENUMBERS", None),
            help="Phone number(s) that will get the notification. Default: read from settings."
        )
        parser.add_argument(
            "--accesskey",
            default=getattr(settings, "MESSAGEBIRD_ACCESS_KEY", None),
            help="Messagebird API key. Default: read from settings."
        )
        parser.add_argument(
            "--originator",
            default=getattr(settings, "MESSAGEBIRD_ORIGINATOR", None),
            help="Messagebird API key. Default: read from settings."
        )
        parser.add_argument(
            "--blacklist",
            nargs="*",
            default=getattr(settings, "PROJECTS_NOTIFICATION_BLACKLIST", None),
            help="ids or slugs of the project(s) which shouldn't be taken into account when retrieving issues."
        )

    def raise_command_error(self, error: messagebird.ErrorException, action: str) -> NoReturn:
        message = f"Failed to {action}. The following error{'s' if len(error.errors) > 1 else ''} happened:\n"
        message += "\n".join(f"{e.description} (code: {e.code})" for e in error.errors)
        raise CommandError(message)

    def check_balance(self) -> None:
        try:
            balance = self.client.balance()
        except messagebird.ErrorException as e:
            self.raise_command_error(e, "request balance")
        self.stdout.write(self.style.SUCCESS(f"Current balance: {balance.amount}."))

    def send_message(self, message: str, originator: str, recipients: List[str]) -> Message:
        try:
            return self.client.message_create(
                originator,
                recipients,
                message
            )
        except messagebird.ErrorException as e:
            self.raise_command_error(e, "send message")

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
        if options["phonenumbers"] is None:
            raise CommandError("No phone numbers provided, and none are found in settings.")
        if options["accesskey"] is None:
            raise CommandError("No Messagebird access key provided, and is not found in settings.")
        if options["originator"] is None:
            raise CommandError("No Messagebird originator provided, and is not found in settings.")
        if not 3 <= len(options["originator"]) <= 11:
            raise CommandError(f"Messagebird originator {options['originator']} must be between 3 and 11 characters.")

        self.client = messagebird.Client(options["accesskey"])
        self.check_balance()

        for number in options["phonenumbers"]:
            if not number.startswith("+"):
                raise CommandError(f"Invalid number format: {number}. The number must start with a country prefix (e.g. +31).")
            if not number.startswith("+31"):
                self.stdout.write(self.style.WARNING(f"Warning: {number} is not a Dutch number. Prices might differ."))

        issues = self.get_issues(options["severity"], options["priority"], options["last_updated"], options["blacklist"])
        self.issues = issues

        if issues.exists():
            issues_str = "\n".join(f"#{issue.ref}: {issue.subject} ({issue.project.slug})" for issue in issues)

            # Should use Django pluralization instead, but messages should be sent in English
            message = (
                f"Taiga alert: the following issue{'s were' if issues.count() > 1 else ' was'} recently set to {options['severity']}/{options['priority']}"
                f"{' or higher' if options['severity'] != 'critical' or options['priority'] != 'high' else ''}:\n"
            )
            message += issues_str
            self.stdout.write(f"The following issues were found:\n{issues_str}")

            message_info = self.send_message(message, options["originator"], options["phonenumbers"])

            if message_info.recipients["totalCount"] != message_info.recipients["totalSentCount"]:
                style = self.style.NOTICE
            else:
                style = self.style.SUCCESS
            self.stdout.write(
                style(f"{message_info.recipients['totalCount']} messages in total, {message_info.recipients['totalSentCount']} sent.")
            )
        else:
            self.stdout.write("No corresponding issues found.")

        return "End of command."
