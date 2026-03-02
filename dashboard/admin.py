from django.contrib import admin
from .models import Building, Event, PhaseOccupancy


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "building_type", "capacity", "occupancy")
    list_filter = ("building_type",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "location", "event_date", "start_time", "end_time")
    list_filter = ("event_date", "location")
    ordering = ("event_date", "start_time")


@admin.register(PhaseOccupancy)
class PhaseOccupancyAdmin(admin.ModelAdmin):
    list_display = ("building", "time_phase", "expected_percentage")
    list_filter = ("time_phase", "building")