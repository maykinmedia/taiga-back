# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos Ventures SL

"""Admin list filters and helpers shared by the issues, tasks and
userstories admin, so the "global overview across projects" admin
pages stay consistent without triplicating the same filter code."""

from django.contrib import admin
from django.utils.safestring import mark_safe

from taiga.base.utils.urls import get_absolute_url
from taiga.front.urls import urls as front_urls
from taiga.projects.models import Project
from taiga.users.models import User


class SuperuserListFilter(admin.SimpleListFilter):
    title = "Assigned to Maykiner"
    parameter_name = "maykiners"

    def lookups(self, request, model_admin):
        qs = User.objects.filter(email__icontains='maykinmedia.nl', is_active=True).order_by('full_name')
        return [('None', 'None'), ('Me', 'Me')] + [(u.id, u.full_name) for u in qs]

    def queryset(self, request, queryset):
        if self.value():
            if self.value() == 'None':
                return queryset.filter(assigned_to__isnull=True)
            elif self.value() == 'Me':
                return queryset.filter(assigned_to=request.user)
            else:
                return queryset.filter(assigned_to__id=self.value())


class ClosedOpenListFilter(admin.SimpleListFilter):
    """Filters on an "is closed" boolean lookup. Issue and Task expose this
    via their `status`, while UserStory has its own `is_closed` field, so
    subclass and override `lookup_field` where the default doesn't apply."""
    title = "Closed or Open"
    parameter_name = "closed_open"
    lookup_field = "status__is_closed"

    def lookups(self, request, model_admin):
        return [
            ('open', 'Open'),
            ('closed', 'Closed')
        ]

    def queryset(self, request, queryset):
        if self.value():
            if self.value() == 'open':
                return queryset.filter(**{self.lookup_field: False})
            if self.value() == 'closed':
                return queryset.filter(**{self.lookup_field: True})


class TagsArrayFieldListFilter(admin.SimpleListFilter):
    """An admin list filter for the model's own `tags` ArrayField."""
    title = "Tags"
    parameter_name = "tags"

    def lookups(self, request, model_admin):
        """Return the filtered queryset."""
        queryset_values = model_admin.model.objects.values_list(
            self.parameter_name, flat=True
        )
        values = []
        for sublist in queryset_values:
            if sublist:
                for value in sublist:
                    if value:
                        values.append((value, value))
            else:
                values.append(("null", "-"))
        return sorted(set(values))

    def queryset(self, request, queryset):
        """Return the filtered queryset."""
        lookup_value = self.value()
        if lookup_value:
            lookup_filter = (
                {"{}__isnull".format(self.parameter_name): True}
                if lookup_value == "null"
                else {"{}__contains".format(self.parameter_name): [lookup_value]}
            )
            queryset = queryset.filter(**lookup_filter)
        return queryset


class ProjectTagsArrayFieldListFilter(admin.SimpleListFilter):
    """An admin list filter for the parent project's `tags` ArrayField."""
    title = "Project tags"
    parameter_name = "project_tags"

    def lookups(self, request, model_admin):
        """Return the filtered queryset."""
        queryset_values = Project.objects.values_list(
            "tags", flat=True
        )
        values = []
        for sublist in queryset_values:
            if sublist:
                for value in sublist:
                    if value:
                        values.append((value, value))
            else:
                values.append(("null", "-"))
        return sorted(set(values))

    def queryset(self, request, queryset):
        """Return the filtered queryset."""
        lookup_value = self.value()
        if lookup_value:
            lookup_filter = (
                {"project__tags__isnull": True}
                if lookup_value == "null"
                else {"project__tags__contains": [lookup_value]}
            )
            queryset = queryset.filter(**lookup_filter)
        return queryset


def custom_titled_filter(title):
    class Wrapper(admin.FieldListFilter):
        def __new__(cls, *args, **kwargs):
            instance = admin.FieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance
    return Wrapper


def get_front_ref_link(obj, front_url_type):
    """Clickable link to `obj`'s ref, pointing at its front-end detail page.
    `front_url_type` is a key into taiga.front.urls.urls (e.g. "issue",
    "task", "userstory") so each admin gets the right URL shape (userstories
    are served under /us/ rather than /userstory/)."""
    path = front_urls[front_url_type].format(obj.project.slug, obj.ref)
    return mark_safe("<a target='_blank' href='{}'>{}</a>".format(get_absolute_url(path), obj.ref))


def get_front_subject_link(obj, front_url_type):
    """Same as `get_front_ref_link`, but displaying the subject as link text."""
    path = front_urls[front_url_type].format(obj.project.slug, obj.ref)
    return mark_safe("<a target='_blank' href='{}'>{}</a>".format(get_absolute_url(path), obj.subject))
