import pytest

from django.urls import reverse

from tests import factories as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    superuser = f.UserFactory(username="admin", is_superuser=True, is_staff=True)
    client.login(superuser)
    return client


@pytest.fixture
def issues(settings):
    support_1 = f.UserFactory(username="support1", full_name="Support One")
    support_2 = f.UserFactory(username="support2", full_name="Support Two")
    other = f.UserFactory(username="other", full_name="Other User")
    settings.SUPPORT_USERNAMES = ["support1", "support2"]
    return {
        "support_1": f.IssueFactory(assigned_to=support_1),
        "support_2": f.IssueFactory(assigned_to=support_2),
        "other": f.IssueFactory(assigned_to=other),
        "unassigned": f.IssueFactory(assigned_to=None),
    }


def get_changelist_issues(client, **params):
    response = client.get(reverse("admin:issues_issue_changelist"), params)
    assert response.status_code == 200
    return set(response.context["cl"].queryset)


def test_changelist_without_support_filter_returns_all_issues(admin_client, issues):
    assert get_changelist_issues(admin_client) == set(issues.values())


def test_support_filter_all_returns_only_support_issues(admin_client, issues):
    result = get_changelist_issues(admin_client, support="all")

    assert result == {issues["support_1"], issues["support_2"]}


def test_support_filter_single_member_returns_only_their_issues(admin_client, issues):
    user_id = issues["support_1"].assigned_to.id

    result = get_changelist_issues(admin_client, support=user_id)

    assert result == {issues["support_1"]}


def test_support_filter_ignores_users_that_are_not_support(admin_client, issues):
    user_id = issues["other"].assigned_to.id

    result = get_changelist_issues(admin_client, support=user_id)

    assert result == set()


def test_support_filter_excludes_inactive_support_members(admin_client, issues):
    support_2 = issues["support_2"].assigned_to
    support_2.is_active = False
    support_2.save()

    result = get_changelist_issues(admin_client, support="all")

    assert result == {issues["support_1"]}


def test_support_filter_lists_support_members_as_choices(admin_client, issues):
    response = admin_client.get(reverse("admin:issues_issue_changelist"))

    changelist = response.context["cl"]
    support_filter = next(
        spec for spec in changelist.filter_specs
        if getattr(spec, "parameter_name", None) == "support"
    )
    # The first choice is Django's own (translated) "All" option.
    choices = [choice["display"] for choice in support_filter.choices(changelist)][1:]
    assert choices == [
        "All support members",
        "Support One",
        "Support Two",
    ]


def test_support_filter_without_configured_usernames(admin_client, issues, settings):
    settings.SUPPORT_USERNAMES = []

    assert get_changelist_issues(admin_client, support="all") == set()
