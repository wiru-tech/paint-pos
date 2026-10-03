"""Sweep stock levels and alert managers about anything at/below threshold.

Run it on a schedule (cron / Task Scheduler):

    python manage.py check_low_stock --email

In-app notifications always fire; ``--email`` also sends a copy through the
configured EMAIL_BACKEND (console in development).
"""
from django.core.management.base import BaseCommand

from core.models import Branch
from inventory.services import scan_low_stock


class Command(BaseCommand):
    help = "Create low-stock notifications for managers (optionally e-mail them)."

    def add_arguments(self, parser):
        parser.add_argument("--branch", help="Limit the sweep to one branch code, e.g. DTN")
        parser.add_argument("--email", action="store_true", help="Also send an e-mail copy")

    def handle(self, *args, **options):
        branch = None
        if options["branch"]:
            branch = Branch.objects.filter(code__iexact=options["branch"]).first()
            if branch is None:
                self.stderr.write(self.style.ERROR(f"No branch with code {options['branch']!r}."))
                return

        created = scan_low_stock(branch=branch, email=options["email"])
        scope = branch.name if branch else "all branches"
        self.stdout.write(self.style.SUCCESS(f"{created} low-stock notification(s) raised for {scope}."))
