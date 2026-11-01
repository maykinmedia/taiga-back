import ipaddress
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.views import View
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest

from .collectors import IssueCollector

registry = CollectorRegistry()
registry.register(IssueCollector())


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Return the client IP address, only trusting X-Forwarded-For entries added by our own proxies.

    Each proxy appends the address it received the request from, so the n-th entry from the right
    (n = METRICS_NUM_PROXIES) is the address the outermost proxy saw. Entries further to the left
    are supplied by the client and can't be trusted.
    """
    num_proxies = settings.METRICS_NUM_PROXIES
    if not num_proxies:
        return request.META.get("REMOTE_ADDR")

    forwarded_for = [
        ip.strip() for ip in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if ip.strip()
    ]
    if len(forwarded_for) < num_proxies:
        return None
    return forwarded_for[-num_proxies]


def is_ip_allowed(ip: Optional[str]) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False

    return any(
        address in ipaddress.ip_network(network, strict=False)
        for network in settings.METRICS_ALLOWED_IPS
    )


class MetricsView(View):
    """
    Prometheus metrics, only accessible from the IP addresses in METRICS_ALLOWED_IPS.
    """

    def get(self, request: HttpRequest) -> HttpResponse:
        if not is_ip_allowed(get_client_ip(request)):
            return HttpResponseForbidden()

        return HttpResponse(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)
