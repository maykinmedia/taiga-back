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
def projects():
    return {
        "backend": f.ProjectFactory(tags=["backend", "django"]),
        "frontend": f.ProjectFactory(tags=["frontend"]),
        "untagged": f.ProjectFactory(tags=[]),
        "null_tags": f.ProjectFactory(tags=None),
    }


def get_changelist(client, **params):
    response = client.get(reverse("admin:projects_project_changelist"), params)
    assert response.status_code == 200
    return response


def get_changelist_projects(client, **params):
    return set(get_changelist(client, **params).context["cl"].queryset)


def test_changelist_shows_project_tags_as_filter_links(admin_client, projects):
    response = get_changelist(admin_client)

    content = response.rendered_content
    assert "<a href='?tags=backend'>backend</a>, <a href='?tags=django'>django</a>" in content
    assert "<a href='?tags=frontend'>frontend</a>" in content


def test_changelist_escapes_project_tags(admin_client):
    f.ProjectFactory(tags=["<script>alert(1)</script>"])

    response = get_changelist(admin_client)

    content = response.rendered_content
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


def test_changelist_without_tags_filter_returns_all_projects(admin_client, projects):
    assert get_changelist_projects(admin_client) == set(projects.values())


def test_tags_filter_offers_all_project_tags(admin_client, projects):
    response = get_changelist(admin_client)

    tags_filter = next(
        spec for spec in response.context["cl"].filter_specs if spec.parameter_name == "tags"
    )
    assert [value for value, _ in tags_filter.lookup_choices] == [
        "backend", "django", "frontend", "null",
    ]


def test_tags_filter_returns_projects_with_tag(admin_client, projects):
    result = get_changelist_projects(admin_client, tags="django")

    assert result == {projects["backend"]}


def test_tags_filter_with_unknown_tag_returns_nothing(admin_client, projects):
    assert get_changelist_projects(admin_client, tags="unknown") == set()


def test_tags_filter_without_tags_returns_untagged_projects(admin_client, projects):
    result = get_changelist_projects(admin_client, tags="null")

    assert result == {projects["untagged"], projects["null_tags"]}
