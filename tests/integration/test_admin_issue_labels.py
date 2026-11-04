import pytest

from django.urls import reverse

from taiga.projects.issues.admin import get_label_color
from tests import factories as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    superuser = f.UserFactory(username="admin", is_superuser=True, is_staff=True)
    client.login(superuser)
    return client


def get_changelist(client):
    response = client.get(reverse("admin:issues_issue_changelist"))
    assert response.status_code == 200
    return response


def test_changelist_includes_label_stylesheet(admin_client):
    response = get_changelist(admin_client)

    assert "issues/admin/labels.css" in response.rendered_content


def test_labels_use_css_class_and_color_variable(admin_client):
    issue = f.IssueFactory()
    issue.type.name = "Bug"
    issue.type.color = "#E44057"
    issue.type.save()

    response = get_changelist(admin_client)

    assert (
        "<a href='?type__name=Bug' class='issue-label' style='--label-color: #E44057;'>Bug</a>"
        in response.rendered_content
    )


def test_labels_for_severity_and_priority(admin_client):
    issue = f.IssueFactory()
    issue.severity.name = "Critical"
    issue.severity.save()
    issue.priority.name = "High"
    issue.priority.save()

    content = get_changelist(admin_client).rendered_content

    assert "<a href='?severity__name=Critical' class='issue-label'" in content
    assert "<a href='?priority__name=High' class='issue-label'" in content


def test_label_name_is_escaped(admin_client):
    issue = f.IssueFactory()
    issue.type.name = "<script>alert('type')</script>"
    issue.type.save()

    content = get_changelist(admin_client).rendered_content

    assert "<script>alert('type')</script>" not in content
    assert "&lt;script&gt;alert(&#39;type&#39;)&lt;/script&gt;" in content


def test_label_name_is_url_encoded_in_link(admin_client):
    issue = f.IssueFactory()
    issue.type.name = "Bug & feature"
    issue.type.save()

    content = get_changelist(admin_client).rendered_content

    assert "<a href='?type__name=Bug+%26+feature' class='issue-label'" in content


def test_label_with_invalid_color_uses_default_color(admin_client):
    issue = f.IssueFactory()
    issue.type.color = "red' onclick='x"
    issue.type.save()

    content = get_changelist(admin_client).rendered_content

    assert "onclick" not in content
    assert "--label-color: #999999;" in content


def test_issue_without_type_severity_and_priority(admin_client):
    f.IssueFactory(type=None, severity=None, priority=None)

    get_changelist(admin_client)


@pytest.mark.parametrize("color", ["#E44057", "#e44057", "#abc"])
def test_get_label_color_accepts_hex_colors(color):
    assert get_label_color(color) == color


@pytest.mark.parametrize("color", [None, "", "red", "#12345", "#E44057;", "url(x)"])
def test_get_label_color_rejects_other_values(color):
    assert get_label_color(color) == "#999999"
