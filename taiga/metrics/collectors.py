from django.db.models import Count
from prometheus_client.core import GaugeMetricFamily

from taiga.projects.issues.models import Issue

ISSUE_LABELS = ["project", "status", "closed", "type", "severity", "priority"]


class IssueCollector:
    """
    Expose the current number of issues per project, broken down by status, type, severity and
    priority. Issues of blocked projects are left out.
    """

    def collect(self):
        gauge = GaugeMetricFamily(
            "taiga_issues",
            "Number of Taiga issues per project",
            labels=ISSUE_LABELS,
        )

        rows = (
            Issue.objects.filter(project__blocked_code__isnull=True)
            .values(
                "project__slug",
                "status__name",
                "status__is_closed",
                "type__name",
                "severity__name",
                "priority__name",
            )
            .annotate(count=Count("id"))
            .order_by()
        )
        for row in rows:
            gauge.add_metric(
                [
                    row["project__slug"],
                    row["status__name"] or "",
                    "true" if row["status__is_closed"] else "false",
                    row["type__name"] or "",
                    row["severity__name"] or "",
                    row["priority__name"] or "",
                ],
                row["count"],
            )

        yield gauge
