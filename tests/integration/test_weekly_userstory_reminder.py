from datetime import timedelta

import pytest

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from taiga.projects.management.commands.send_weekly_userstory_reminder import Command
from tests.factories import ProjectFactory, UserFactory, UserStoryFactory, UserStoryStatusFactory

pytestmark = pytest.mark.django_db


def test_columns_ordered_left_to_right_and_userstories_by_due_date():
    today = timezone.localdate()
    project = ProjectFactory()
    user = UserFactory()
    status_right = UserStoryStatusFactory(project=project, name="Done-ish", order=2)
    status_left = UserStoryStatusFactory(project=project, name="Ready", order=1)
    us_later = UserStoryFactory(project=project, status=status_left, assigned_to=user,
                                due_date=today + timedelta(days=3))
    us_no_due_date = UserStoryFactory(project=project, status=status_left, assigned_to=user,
                                      due_date=None)
    us_overdue = UserStoryFactory(project=project, status=status_left, assigned_to=user,
                                  due_date=today - timedelta(days=2))
    us_right = UserStoryFactory(project=project, status=status_right, assigned_to=user,
                                due_date=today - timedelta(days=10))

    columns = Command().get_columns(project, [us_later, us_no_due_date, us_overdue, us_right])

    assert [column["status"] for column in columns] == [status_left, status_right]
    assert [row["userstory"] for row in columns[0]["userstories"]] == [
        us_overdue, us_no_due_date, us_later
    ]
    assert columns[0]["userstories"][0]["is_overdue"] is True
    assert columns[0]["userstories"][1]["is_overdue"] is False


def test_sends_one_email_per_assigned_user():
    project = ProjectFactory(slug="kanban-project")
    status = UserStoryStatusFactory(project=project, order=1)
    user_a = UserFactory(email="a@example.com")
    user_b = UserFactory(email="b@example.com")
    us_a = UserStoryFactory(project=project, status=status, assigned_to=user_a, subject="Story for A")
    us_b = UserStoryFactory(project=project, status=status, subject="Story for B")
    us_b.assigned_users.add(user_b)

    call_command(Command(), project="kanban-project")

    assert sorted(message.to[0] for message in mail.outbox) == ["a@example.com", "b@example.com"]
    message_a = next(message for message in mail.outbox if message.to == ["a@example.com"])
    html_a = message_a.alternatives[0][0]
    assert "Story for A" in html_a
    assert "Story for B" not in html_a
    assert f"/project/kanban-project/us/{us_a.ref}" in html_a


def test_excludes_closed_archived_and_other_project_userstories():
    project = ProjectFactory(slug="kanban-project")
    user = UserFactory()
    closed_status = UserStoryStatusFactory(project=project, is_closed=True)
    archived_status = UserStoryStatusFactory(project=project, is_archived=True)
    UserStoryFactory(project=project, status=closed_status, assigned_to=user)
    UserStoryFactory(project=project, status=archived_status, assigned_to=user)
    UserStoryFactory(assigned_to=user)

    call_command(Command(), project="kanban-project")

    assert len(mail.outbox) == 0


def test_inactive_users_are_skipped():
    project = ProjectFactory(slug="kanban-project")
    user = UserFactory(is_active=False)
    UserStoryFactory(project=project, status=UserStoryStatusFactory(project=project), assigned_to=user)

    call_command(Command(), project="kanban-project")

    assert len(mail.outbox) == 0


def test_user_filter():
    project = ProjectFactory(slug="kanban-project")
    status = UserStoryStatusFactory(project=project)
    user_a = UserFactory(username="user-a", email="a@example.com")
    user_b = UserFactory(email="b@example.com")
    UserStoryFactory(project=project, status=status, assigned_to=user_a)
    UserStoryFactory(project=project, status=status, assigned_to=user_b)

    call_command(Command(), project="kanban-project", user=["user-a"])

    assert [message.to for message in mail.outbox] == [["a@example.com"]]


def test_dry_run_sends_nothing():
    project = ProjectFactory(slug="kanban-project")
    UserStoryFactory(project=project, status=UserStoryStatusFactory(project=project),
                     assigned_to=UserFactory())

    call_command(Command(), project="kanban-project", dry_run=True)

    assert len(mail.outbox) == 0


def test_unknown_project():
    with pytest.raises(CommandError):
        call_command(Command(), project="does-not-exist")
