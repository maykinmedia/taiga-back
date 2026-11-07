import pytest

from django.urls import reverse

from taiga.projects.serializers import MembershipDictSerializer
from tests import factories as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def project_members(settings):
    settings.PINNED_ASSIGNEE_USERNAMES = ["sales", "support", "devops"]
    project = f.create_project()
    members = {}
    for username in ["support", "devops", "sales", "alice"]:
        user = f.UserFactory(username=username)
        f.create_membership(project=project, user=user)
        members[username] = user
    return project, members


def get_pinned_orders(response):
    assert response.status_code == 200
    return {m["username"]: m["pinned_order"] for m in response.data["members"]}


def test_project_detail_members_have_pinned_order(client, project_members):
    project, members = project_members
    client.login(members["alice"])

    response = client.json.get(reverse("projects-detail", kwargs={"pk": project.pk}))

    assert get_pinned_orders(response) == {
        "sales": 0,
        "support": 1,
        "devops": 2,
        "alice": None,
    }


def test_project_by_slug_members_have_pinned_order(client, project_members):
    project, members = project_members
    client.login(members["alice"])

    response = client.json.get(reverse("projects-by-slug"), {"slug": project.slug})

    assert get_pinned_orders(response)["support"] == 1


def test_project_detail_without_pinned_usernames(client, project_members, settings):
    settings.PINNED_ASSIGNEE_USERNAMES = []
    project, members = project_members
    client.login(members["alice"])

    response = client.json.get(reverse("projects-detail", kwargs={"pk": project.pk}))

    assert set(get_pinned_orders(response).values()) == {None}


def test_pinned_order_matches_exact_username(settings):
    settings.PINNED_ASSIGNEE_USERNAMES = ["support"]
    member = {
        "id": 1, "username": "Support", "full_name": "", "email": "",
        "photo": None, "role": 1, "role_name": "", "is_active": True, "color": "",
    }

    assert MembershipDictSerializer(member).data["pinned_order"] is None
