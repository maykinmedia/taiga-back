import pytest

from django.urls import reverse

from tests.factories import (IssueFactory, IssueStatusFactory, IssueTypeFactory, PriorityFactory,
                             ProjectFactory, SeverityFactory)

pytestmark = pytest.mark.django_db


@pytest.fixture
def metrics_settings(settings):
    settings.METRICS_ALLOWED_IPS = ["10.0.0.5", "192.168.1.0/24"]
    settings.METRICS_NUM_PROXIES = 0
    return settings


def test_metrics_allowed_ip(client, metrics_settings):
    project = ProjectFactory(slug="metrics-project")
    open_status = IssueStatusFactory(project=project, name="New", is_closed=False)
    closed_status = IssueStatusFactory(project=project, name="Done", is_closed=True)
    labels = {
        "type": IssueTypeFactory(project=project, name="Bug"),
        "severity": SeverityFactory(project=project, name="Normal"),
        "priority": PriorityFactory(project=project, name="High"),
    }
    IssueFactory.create_batch(2, project=project, status=open_status, **labels)
    IssueFactory(project=project, status=closed_status, **labels)

    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.5")

    assert response.status_code == 200
    content = response.content.decode()
    open_lines = [line for line in content.splitlines()
                  if 'project="metrics-project"' in line and 'status="New"' in line]
    closed_lines = [line for line in content.splitlines()
                    if 'project="metrics-project"' in line and 'status="Done"' in line]
    assert len(open_lines) == 1
    assert 'closed="false"' in open_lines[0]
    assert 'type="Bug"' in open_lines[0]
    assert 'severity="Normal"' in open_lines[0]
    assert 'priority="High"' in open_lines[0]
    assert open_lines[0].endswith(" 2.0")
    assert 'closed="true"' in closed_lines[0]
    assert closed_lines[0].endswith(" 1.0")


def test_metrics_excludes_blocked_projects(client, metrics_settings):
    IssueFactory(project=ProjectFactory(slug="blocked-project", blocked_code="blocked-by-staff"))

    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.5")

    assert response.status_code == 200
    assert "blocked-project" not in response.content.decode()


def test_metrics_allowed_network(client, metrics_settings):
    response = client.get(reverse("metrics"), REMOTE_ADDR="192.168.1.77")

    assert response.status_code == 200


def test_metrics_forbidden_ip(client, metrics_settings):
    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.6")

    assert response.status_code == 403


def test_metrics_forbidden_when_no_ips_configured(client, metrics_settings):
    metrics_settings.METRICS_ALLOWED_IPS = []

    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.5")

    assert response.status_code == 403


def test_metrics_ignores_x_forwarded_for_without_proxies(client, metrics_settings):
    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.6", HTTP_X_FORWARDED_FOR="10.0.0.5")

    assert response.status_code == 403


def test_metrics_behind_proxy(client, metrics_settings):
    metrics_settings.METRICS_NUM_PROXIES = 1

    response = client.get(reverse("metrics"), REMOTE_ADDR="172.18.0.2", HTTP_X_FORWARDED_FOR="10.0.0.5")

    assert response.status_code == 200


def test_metrics_behind_proxy_spoofed_x_forwarded_for(client, metrics_settings):
    metrics_settings.METRICS_NUM_PROXIES = 1

    # The client sent "X-Forwarded-For: 10.0.0.5" itself; the proxy appended the real address.
    response = client.get(reverse("metrics"), REMOTE_ADDR="172.18.0.2",
                          HTTP_X_FORWARDED_FOR="10.0.0.5, 203.0.113.9")

    assert response.status_code == 403


def test_metrics_behind_proxy_missing_x_forwarded_for(client, metrics_settings):
    metrics_settings.METRICS_NUM_PROXIES = 1

    response = client.get(reverse("metrics"), REMOTE_ADDR="10.0.0.5")

    assert response.status_code == 403
