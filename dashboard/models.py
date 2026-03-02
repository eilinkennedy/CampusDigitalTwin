from django.db import models


class Building(models.Model):

    BUILDING_TYPE_CHOICES = [
        ("ACADEMIC", "Academic Block"),
        ("HOSTEL", "Hostel"),
        ("CANTEEN", "Canteen"),
        ("LIBRARY", "Library"),
        ("ADMIN", "Administrative Block"),
        ("SHOP", "Shops"),
        ("AUDITORIUM", "Auditorium"),
    ]

    name = models.CharField(max_length=100)
    building_type = models.CharField(
        max_length=20,
        choices=BUILDING_TYPE_CHOICES,
        default="ACADEMIC"
    )
    capacity = models.IntegerField()
    occupancy = models.IntegerField()

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=200)

    # ✅ DROPDOWN LOCATION (ForeignKey)
    location = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="events"
    )

    event_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.title} ({self.event_date})"


class PhaseOccupancy(models.Model):

    TIME_PHASE_CHOICES = [
        ("CLASS_HOURS", "Class Hours"),
        ("SHORT_BREAK", "Short Break"),
        ("LUNCH_BREAK", "Lunch Break"),
        ("ACTIVITIES", "Activities"),
        ("OFF_HOURS", "Off Hours"),
        ("NIGHT", "Night"),
    ]

    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    time_phase = models.CharField(max_length=20, choices=TIME_PHASE_CHOICES)
    expected_percentage = models.IntegerField(
        help_text="Expected occupancy percentage for this phase"
    )

    class Meta:
        unique_together = ("building", "time_phase")

    def __str__(self):
        return f"{self.building.name} - {self.time_phase}"