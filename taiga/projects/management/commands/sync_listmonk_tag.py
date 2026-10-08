"""
This is an additional Taiga Django command to sync users from Taiga projects 
that have a specific tag, to a specific Mailmonk mailinglist.

Examples:

manage.py sync_listmonk_tag --tag=openformulieren --list_id=3 --exclude=maykinmedia.nl  # Open Formulieren gebruikersgroep

"""
import requests

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from taiga.projects.models import Project
from taiga.users.models import User


# LISTMONK_URL, LISTMONK_USER and LISTMONK_TOKEN come from the settings
# (settings/config.py).

TAIGA_TAG_LIST_MAPPING = {
    # Taiga tags: Listmonk list IDs
    "openformulieren": [3, 4], # Open Formulieren gebruikersgroep + SaaS
    "opengegevenslaag": [5, 16],  # Open Gegevenslaag gebruikersgroep + SaaS & On Premise
    "openzaak": [5, 16],
    "openinwoner": [6, 11],  # Open Inwoner gebruikersgroep + SaaS
    "openarchiefbeheer": [7],  # Open Archiefbeheer gebruikersgroep
    "gppwoo": [15],  # GPP Woo SaaS
    "signalen": [14],  # Signalen SaaS
}


class Command(BaseCommand):
    help = (
        "Synchronize Taiga users matching a project tag to a listmonk list. "
        "If no tag and list_id are provided, a default mapping will be used. "
        "Dry-run by default; use --apply to make changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tag",
            default=None,
            help="Project tag to search for",
        )
        parser.add_argument(
            "--list_id",
            type=int,
            default=None,
            help="listmonk list ID",
        )
        parser.add_argument(
            "--exclude-domain",
            default=None,
            help="Email domain to exclude, e.g. example.com",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually make changes. Without this option the command is a dry run.",
        )

    def handle(self, *args, **options):
        tag = options["tag"]
        list_id = options["list_id"]
        exclude_domain = options["exclude_domain"]
        apply = options["apply"]

        if not getattr(settings, "LISTMONK_URL", None):
            raise CommandError("LISTMONK_URL is not configured")

        if not getattr(settings, "LISTMONK_USER", None):
            raise CommandError("LISTMONK_USER is not configured")

        if not getattr(settings, "LISTMONK_TOKEN", None):
            raise CommandError("LISTMONK_TOKEN is not configured")

        if list_id is None and tag is None:
            self.stdout.write("Using default mapping.")
            for internal_tag, internal_list_ids in TAIGA_TAG_LIST_MAPPING.items():
                for internal_list_id in internal_list_ids:
                    self.run(internal_tag, internal_list_id, exclude_domain, apply)
        elif list_id is not None and tag is not None:
            self.run(tag, list_id, exclude_domain, apply)
        else:
           raise CommandError("Both tag and list_id are either provided or left empy.")


    def run(self, tag, list_id, exclude_domain, apply):

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — no changes will be made. Use --apply to make changes."
                )
            )

        session = requests.Session()
        session.auth = (
            settings.LISTMONK_USER,
            settings.LISTMONK_TOKEN,
        )
        session.headers.update({
            "Content-Type": "application/json",
        })

        # Get all subscribers currently in the target list.
        existing_in_list = self.get_list_subscribers(
            session,
            list_id,
        )

        self.stdout.write(
            f"Found {len(existing_in_list)} subscribers in list {list_id}."
        )

        # Get the Taiga users matching the project tag.
        users = (
            User.objects
            .filter(projects__tags__contains=[tag])
            .exclude(email__isnull=True)
            .exclude(email="")
            .values("email", "full_name")
            .distinct()
        )

        added = 0
        already_present = 0
        excluded = 0

        for user in users:
            email = user["email"].strip().lower()

            if exclude_domain and email.endswith(
                "@" + exclude_domain.lstrip("@").lower()
            ):
                excluded += 1
                self.stdout.write(
                    f"EXCLUDED  {email}"
                )
                continue

            if email in existing_in_list:
                already_present += 1
                self.stdout.write(
                    f"EXISTS    {email}"
                )
                continue

            if not apply:
                self.stdout.write(
                    self.style.WARNING(f"WOULD ADD {email}")
                )
                added += 1
                continue

            subscriber = self.find_subscriber(
                session,
                email,
            )

            if subscriber:
                self.add_to_list(
                    session,
                    subscriber["id"],
                    list_id,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"ADDED     {email} (existing subscriber)"
                    )
                )
            else:
                self.create_subscriber(
                    session,
                    email,
                    user["full_name"] or "",
                    list_id,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"CREATED   {email}"
                    )
                )

            added += 1

        self.stdout.write("")
        self.stdout.write(
            f"Already present: {already_present}"
        )
        self.stdout.write(
            f"Excluded:        {excluded}"
        )
        self.stdout.write(
            f"{'Added' if apply else 'Would add'}:       {added}"
        )

    def get_list_subscribers(self, session, list_id):
        response = session.get(
            f"{settings.LISTMONK_URL}/api/subscribers",
            params={
                "list_id": list_id,
                "per_page": "all",
            },
        )
        response.raise_for_status()

        return {
            subscriber["email"].strip().lower()
            for subscriber in response.json()["data"]["results"]
        }

    def find_subscriber(self, session, email):
        response = session.get(
            f"{settings.LISTMONK_URL}/api/subscribers",
            params={
                "query": f'subscribers.email = "{email}"',
                "per_page": 1,
            },
        )
        response.raise_for_status()

        results = response.json()["data"]["results"]

        return results[0] if results else None

    def create_subscriber(self, session, email, name, list_id):
        response = session.post(
            f"{settings.LISTMONK_URL}/api/subscribers",
            json={
                "email": email,
                "name": name,
                "status": "enabled",
                "lists": [list_id],
                "preconfirm_subscriptions": True,
            },
        )
        response.raise_for_status()

    def add_to_list(self, session, subscriber_id, list_id):
        response = session.put(
            f"{settings.LISTMONK_URL}/api/subscribers/lists",
            json={
                "ids": [subscriber_id],
                "action": "add",
                "target_list_ids": [list_id],
                "status": "confirmed",
            },
        )
        response.raise_for_status()

