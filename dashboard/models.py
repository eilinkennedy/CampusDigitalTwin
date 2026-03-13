from django.db import models
from .utils import calculate_distance


class Building(models.Model):

    BUILDING_TYPE_CHOICES = [
        ("ACADEMIC", "Academic Block"),
        ("HOSTEL", "Hostel"),
        ("CANTEEN", "Canteen"),
        ("LIBRARY", "Library"),
        ("ADMIN", "Administrative Block"),
        ("SHOP", "Shops"),
        ("AUDITORIUM", "Auditorium"),
        ("MAIN_GATE", "Main Gate"),
    ]

    name = models.CharField(max_length=100)
    # geospatial coordinates used for navigation markers and routing
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    building_type = models.CharField(
        max_length=20,
        choices=BUILDING_TYPE_CHOICES,
        default="ACADEMIC", blank=True, null=True
    )
    capacity = models.IntegerField(blank=True, null=True)
    is_navigational_only = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Event(models.Model):

    EVENT_TYPE_CHOICES = [
        ("GENERAL", "General"),
        ("EXAM", "Exam"),
        ("PLACEMENT", "Placement Drive"),
        ("PTA", "PTA Meeting"),
        ("ADMISSION", "Admission"),
    ]

    title = models.CharField(max_length=200)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default="GENERAL"
    )

    location = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="events",
        blank=True,
        null=True,
    )
    locations = models.ManyToManyField(
        Building,
        related_name="multi_location_events",
        blank=True,
    )

    event_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    @property
    def location_names(self):
        names = list(self.locations.order_by("name").values_list("name", flat=True))
        if names:
            return ", ".join(names)
        if self.location:
            return self.location.name
        return "No location selected"

    def __str__(self):
        return f"{self.title} ({self.event_date})"


class PhaseOccupancy(models.Model):

    TIME_PHASE_CHOICES = [
        ("CLASS_HOURS", "Class Hours"),
        ("SHORT_BREAK", "Short Break"),
        ("LUNCH_BREAK", "Lunch Break"),
        ("ACTIVITIES", "Activities"),
        ("OFF_HOURS", "Off Hours"),
    ]

    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    time_phase = models.CharField(max_length=20, choices=TIME_PHASE_CHOICES)
    expected_percentage = models.IntegerField()

    class Meta:
        unique_together = ("building", "time_phase")

    def __str__(self):
        return f"{self.building.name} - {self.time_phase}"


# 🔥 PATH MODEL FOR DIJKSTRA
class Path(models.Model):
    from_building = models.ForeignKey(Building, related_name="paths_from", on_delete=models.CASCADE)
    to_building = models.ForeignKey(Building, related_name="paths_to", on_delete=models.CASCADE)
    distance = models.IntegerField()
    direction_hint = models.TextField()

    def save(self, *args, **kwargs):
        from_lat = self.from_building.latitude
        from_lng = self.from_building.longitude
        to_lat = self.to_building.latitude
        to_lng = self.to_building.longitude

        if None not in (from_lat, from_lng, to_lat, to_lng):
            walking_distance = calculate_distance(from_lat, from_lng, to_lat, to_lng) * 1.15
            self.distance = int(round(walking_distance))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.from_building} → {self.to_building} ({self.distance}m)"

class EnergyConsumption(models.Model):
    SCOPE_CHOICES = [
        ("COLLEGE", "Whole College"),
        ("BUILDING", "Individual Building"),
    ]

    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default="COLLEGE",
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        related_name="energy_consumption_records",
        blank=True,
        null=True,
    )
    year = models.IntegerField()
    month = models.IntegerField()
    energy_consumed_kwh = models.FloatField()
    peak_demand_kw = models.FloatField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        target = self.building.name if self.building else "College"
        return f"{target} - {self.year}-{self.month:02d}"