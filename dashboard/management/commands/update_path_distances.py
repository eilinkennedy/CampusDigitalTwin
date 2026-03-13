from django.core.management.base import BaseCommand

from dashboard.models import Path
from dashboard.utils import calculate_distance


class Command(BaseCommand):
    help = "Recalculate and update all path distances using building coordinates."

    def handle(self, *args, **options):
        updated = 0
        skipped = 0

        queryset = Path.objects.select_related("from_building", "to_building")

        for path in queryset:
            from_lat = path.from_building.latitude
            from_lng = path.from_building.longitude
            to_lat = path.to_building.latitude
            to_lng = path.to_building.longitude

            if None in (from_lat, from_lng, to_lat, to_lng):
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped: {path.from_building.name} -> {path.to_building.name} (missing coordinates)"
                    )
                )
                continue

            walking_distance = calculate_distance(from_lat, from_lng, to_lat, to_lng) * 1.15
            path.distance = int(round(walking_distance))
            path.save(update_fields=["distance"])

            updated += 1
            self.stdout.write(
                f"Updated: {path.from_building.name} -> {path.to_building.name} = {path.distance} meters"
            )

        self.stdout.write(
            self.style.SUCCESS(f"Done. Updated={updated}, Skipped={skipped}")
        )