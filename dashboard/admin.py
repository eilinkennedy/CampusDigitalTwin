from django.contrib import admin
from .models import Building, Event, PhaseOccupancy


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "building_type", "capacity", "occupancy")
    list_filter = ("building_type",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_date", "start_time", "location")
    list_filter = ("event_date",)
    ordering = ("event_date", "start_time")


@admin.register(PhaseOccupancy)
class PhaseOccupancyAdmin(admin.ModelAdmin):
    list_display = ("building", "time_phase", "expected_percentage")
    list_filter = ("time_phase", "building")
