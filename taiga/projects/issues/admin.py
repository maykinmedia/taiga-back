# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.contrib import admin
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.template.response import TemplateResponse
from django.urls import path

from taiga.projects.attachments.admin import AttachmentInline
from taiga.projects.notifications.admin import WatchedInline
from taiga.projects.votes.admin import VoteInline
from taiga.projects.history.utils import attach_total_comments_to_queryset
from taiga.projects.models import Project
from taiga.projects.admin_utils import (
    SuperuserListFilter,
    ClosedOpenListFilter,
    TagsArrayFieldListFilter,
    ProjectTagsArrayFieldListFilter,
    custom_titled_filter,
    get_front_ref_link,
    get_front_subject_link,
)

from . import models

# Borrowed priority/severity filters from Victorien's work in send_sms_notifications
import re
from functools import reduce
from django.db.models import Q

SEVERITY_CHOICES = ["wishlist", "minor", "normal", "important", "critical"]
PRIORITY_CHOICES = ["low", "normal", "high"]
            
def get_filters(severity, priority):
    severity_filters = reduce(
        lambda q1, q2: q1 | q2,
        [Q(severity__name__icontains=severity) for severity in SEVERITY_CHOICES[SEVERITY_CHOICES.index(severity):]]
    )

    priority_filters = reduce(
        lambda q1, q2: q1 | q2,
        [Q(priority__name__icontains=priority) for priority in PRIORITY_CHOICES[PRIORITY_CHOICES.index(priority):]]
    )
    return (severity_filters, priority_filters)


HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
DEFAULT_LABEL_COLOR = "#999999"


def get_label_color(color):
    """Only allow hex colours in the inline style, as the colour of a
    type/severity/priority is set by project admins."""
    return color if color and HEX_COLOR_RE.match(color) else DEFAULT_LABEL_COLOR


class SHTFIssuesListFilter(admin.SimpleListFilter):
    title = "SHTF"
    parameter_name = "shtf"
    def lookups(self, request, model_admin):
        return [
            ('light_shit', '>=Important|High'),
            ('heavy_shit', 'Critical+High')
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            if self.value() == 'light_shit':
                (severity_filters, priority_filters) = get_filters('important', 'high')
                return queryset.filter(severity_filters | priority_filters)
            if self.value() == 'heavy_shit':
                (severity_filters, priority_filters) = get_filters('critical', 'high')
                return queryset.filter(severity_filters | priority_filters)


class IssueAdmin(admin.ModelAdmin):
    list_display = ["get_ref", "get_subject", "project", "get_status", "assigned_to", "get_type", "get_severity", "get_priority", "modified_date", "created_date", "due_date", "owner", "get_activity", "ref", "subject"] # Ref and Subject are required due to system check
    list_display_links = ["ref", "subject",]
    list_filter = [ClosedOpenListFilter,
                   ("type__name", custom_titled_filter("Type")),
                   SHTFIssuesListFilter,
                   ProjectTagsArrayFieldListFilter,
                   SuperuserListFilter,
                   ("severity__name", custom_titled_filter("Severity")),
                   ("priority__name", custom_titled_filter("Priority")),
                   ("status__name", custom_titled_filter("Status")),
                   "project",
                   TagsArrayFieldListFilter]
    inlines = [WatchedInline, VoteInline]
    raw_id_fields = ["project"]
    search_fields = ["subject", "description", "id", "ref", "project__name"]
    date_hierarchy = "created_date"
    ordering = ("-modified_date",)

    class Media:
        css = {"all": ["issues/admin/labels.css"]}

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [path("ofdash/", self.admin_site.admin_view(self.of_dash))]
        return custom_urls + urls

    def of_issues(self, project, match_string_list):
        from operator import or_
        from functools import reduce
        q_expr = reduce(or_, (Q(subject__icontains=s) for s in match_string_list))
        return [models.Issue.objects.filter(project=project).filter(q_expr).order_by('ref').first()]

    def of_wiki(self, project, wiki_slug):
        from taiga.projects.wiki.models import WikiPage
        return WikiPage.objects.filter(project=project, slug=wiki_slug).exists()
    
    def of_dash(self, request):
        context = dict(customers=[])
        of_projects = Project.objects.filter(blocked_code__isnull=True, tags__contains=["openformulieren"]).order_by("-created_date")
        for project in of_projects:
            
            context["customers"] += [{"project": project,
                                      "install": self.of_issues(project, ["Installatie", "Deployment"]),
                                      "access": self.of_issues(project, ["toegang", "gebruikers", "keycloak"]),
                                      "intro": self.of_issues(project, ["introductie", "training"]),
                                      "domain": self.of_issues(project, ["domein"]),
                                      "digid": self.of_issues(project, ["DigiD"]),
                                      "slr": self.of_wiki(project, 'reports')}]
                                     
        return TemplateResponse(request, "of_dashboard.html", context)

    def get_queryset(self, request):
        qs = super(IssueAdmin, self).get_queryset(request)
        qs = attach_total_comments_to_queryset(qs)
        return qs
    
    def get_ref(self, obj):
        return get_front_ref_link(obj, "issue")
    get_ref.short_description = "Ref"
    get_ref.admin_order_field = "ref"

    def get_subject(self, obj):
        return get_front_subject_link(obj, "issue")
    get_subject.short_description = "Subject"
    get_subject.admin_order_field = "subject"

    def get_status(self, obj):
        return str(obj.status)
    get_status.short_description = "Status"
    get_status.admin_order_field = "status__name"

    def get_label(self, field_name, label):
        if label is None:
            return self.get_empty_value_display()
        return format_html(
            "<a href='?{}' class='issue-label' style='--label-color: {};'>{}</a>",
            urlencode({"{}__name".format(field_name): label.name}),
            get_label_color(label.color),
            label.name,
        )

    def get_type(self, obj):
        return self.get_label("type", obj.type)
    get_type.short_description = "type"
    get_type.admin_order_field = "type__name"

    def get_severity(self, obj):
        return self.get_label("severity", obj.severity)
    get_severity.short_description = "severity"
    get_severity.admin_order_field = "severity__name"

    def get_priority(self, obj):
        return self.get_label("priority", obj.priority)
    get_priority.short_description = "priority"
    get_priority.admin_order_field = "priority__name"

    def get_activity(self, obj):
        return mark_safe("{} comments".format(obj.total_comments))
                         
    def get_object(self, *args, **kwargs):
        self.obj = super().get_object(*args, **kwargs)
        return self.obj

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if (db_field.name in ["status", "priority", "severity", "type", "milestone"]
                and getattr(self, 'obj', None)):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                                                      project=self.obj.project)
        elif (db_field.name in ["owner", "assigned_to"]
                and getattr(self, 'obj', None)):
            kwargs["queryset"] = db_field.related_model.objects.filter(
                                         memberships__project=self.obj.project)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if (db_field.name in ["watchers"]
                and getattr(self, 'obj', None)):
            kwargs["queryset"] = db_field.related.parent_model.objects.filter(
                                         memberships__project=self.obj.project)
        return super().formfield_for_manytomany(db_field, request, **kwargs)


admin.site.register(models.Issue, IssueAdmin)
