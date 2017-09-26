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

from django.core.management.base import BaseCommand
from taiga.projects.models import Project, Membership
from taiga.users.models import User

class Command(BaseCommand):
    help = "Assign superuser users to all projects"

    def handle(self, *args, **options):
        superusers = User.objects.filter(is_superuser=True, is_active=True)
        for user in superusers:
            projects = Project.objects.exclude(memberships__user=user).filter(blocked_code=None)
            for project in projects:
                Membership.objects.create(user=user, project=project, is_admin=True,
                                          role=project.roles.all().last())
