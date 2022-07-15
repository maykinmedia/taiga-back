from datetime import timedelta

import pytest
import responses
from messagebird.client import ENDPOINT

from django.core.management import call_command
from django.utils import timezone

from taiga.projects.management.commands.send_sms_notifications import Command
from tests.factories import IssueFactory, SeverityFactory


def create_responses() -> None:
    responses.add(
        responses.GET,
        f"{ENDPOINT}/balance",
        json={
            "payment": "prepaid",
            "type": "euros",
            "amount": 103
        }
    )

    responses.add(
        responses.POST,
        f"{ENDPOINT}/messages",
        json={
            "recipients": {
                "totalCount": 1,
                "totalSentCount": 1,
                "items": [
                    {
                        "recipient": "+123456",
                        "status": "sent"
                    }
                ]
            }
        }
    )

@pytest.mark.django_db
@responses.activate
def test_sms_notifications_ok():
    create_responses()
    severity_critical = SeverityFactory(name="Critical 1")
    issue_critical = IssueFactory(severity=severity_critical)
    cmd = Command()

    call_command(
        cmd,
        severity="important",
        phonenumbers=["+123456"],
        accesskey="accesskey",
        originator="originator"
    )

    assert cmd.issues.count() == 1
    assert cmd.issues.first() == issue_critical

@pytest.mark.django_db
@responses.activate
def test_sms_notifications_nothing():
    create_responses()
    severity_important = SeverityFactory(name="Important 1")
    issue_important = IssueFactory(severity=severity_important)
    severity_critical = SeverityFactory(name="critical 1")
    issue_critical = IssueFactory(
        severity=severity_critical,
        created_date=timezone.now() - timedelta(seconds=10 * 60)
    )

    cmd = Command()

    call_command(
        cmd,
        severity="critical",
        phonenumbers=["+123456"],
        accesskey="accesskey",
        originator="originator"
    )

    assert cmd.issues.count() == 0
