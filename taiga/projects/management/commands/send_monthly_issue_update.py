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

from django.conf import settings
from django.core.management.base import BaseCommand

from taiga.base.utils.urls import get_absolute_url
from taiga.projects.issues.models import Issue
from taiga.projects.models import Project
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
            issue_types = []
            nr_bugs = 0
            for issue_type in project.issue_types.all():
                nr = project_issues.filter(type=issue_type).count()
                if nr:
                    if issue_type.name == 'Bug':
                        nr_bugs = nr
                    issue_types += [{'nr': nr,
                                     'name': issue_type.name,
                                     'color': issue_type.color}]
            projects_with_issues += [{'project': project, 'issues': project_issues, 'nr_bugs': nr_bugs,
                                      'url': url, 'nr_issues': nr_issues, 'issue_types': issue_types}]
        projects_with_issues = sorted(projects_with_issues,
                                      key=lambda project: project['nr_bugs'], reverse=True)
        context = {'projects': projects_with_issues,
                   'summary': "".join([u"- {}: {} ".format(p['project'], p['nr_bugs']) for p in projects_with_issues])}
        
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
