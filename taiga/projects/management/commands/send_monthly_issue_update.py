# -*- coding: utf-8 -*-
# Copyright (C) 2014-2017 Andrey Antukh <niwi@niwi.nz>
# Copyright (C) 2014-2017 Jesús Espino <jespinog@gmail.com>
# Copyright (C) 2014-2017 David Barragán <bameda@dbarragan.com>
# Copyright (C) 2014-2017 Alejandro Alonso <alejandro.alonso@kaleidos.net>
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Count

from taiga.base.utils.urls import get_absolute_url
from taiga.projects.models import Project, Membership
from taiga.projects.issues.models import Issue
from taiga.projects.notifications.models import HistoryChangeNotification
from taiga.users.models import User

NOTIFY_ISSUES_TO_SU_INTERVAL = 3600 * 24

class Command(BaseCommand):
    help = "Update superusers with 'notify issues' in their biography on any new or updated issues. To be run once per day"


    def send_issue_notification(self, users):
        from taiga.projects.notifications.services import _make_template_mail, make_ms_thread_index
        domain = settings.SITES["api"]["domain"].split(":")[0] or settings.SITES["api"]["domain"]

        issues = Issue.objects.filter(status__is_closed=False)
        projects = Project.objects.filter(issues__in=issues, blocked_code__isnull=True).distinct()

        projects_with_issues = []
        for project in projects:
            url = get_absolute_url('/project/{}/issue'.format(project.slug))
            project_issues = issues.filter(project=project).distinct()
            nr_issues = project_issues.count()
            projects_with_issues += [(project, project_issues, url, nr_issues)]
        projects_with_issues = sorted(projects_with_issues, key=lambda project: project[3], reverse=True)
        
        context = {'projects': projects_with_issues,
                   'summary': "".join([u"- {}: {} ".format(p[0], p[3]) for p in projects_with_issues])}
        
        email = _make_template_mail('issues/issues-list-monthly')

        msg_id = 'taiga-system'
        now = datetime.datetime.now()
        format_args = {
            "project_name": 'taiga-system',
            "project_slug": 'taiga-system',
            "msg_id": msg_id,
            "time": int(now.timestamp()),
            "domain": domain
        }

        headers = {
            "Message-ID": "<{project_slug}/{msg_id}/{time}@{domain}>".format(**format_args),
            "In-Reply-To": "<{project_slug}/{msg_id}@{domain}>".format(**format_args),
            "References": "<{project_slug}/{msg_id}@{domain}>".format(**format_args),
            "List-ID": 'Taiga/{project_name} <taiga.{project_slug}@{domain}>'.format(**format_args),
            "Thread-Index": make_ms_thread_index("<{project_slug}/{msg_id}@{domain}>".format(**format_args), now)
        }

        for user in users:
            context["user"] = user
            context["lang"] = user.lang or settings.LANGUAGE_CODE
            email.send(user.email, context, headers=headers)
    
    def handle(self, *args, **options):
        superusers = User.objects.filter(is_superuser=True, is_active=True, bio__icontains='notify issues')
        self.send_issue_notification(superusers)
