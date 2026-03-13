from django.contrib import admin
from .models import Building, EnergyConsumption, Event, PhaseOccupancy, Path


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "building_type", "capacity")
    list_filter = ("building_type",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "event_type", "display_locations", "event_date", "start_time", "end_time")
    list_filter = ("event_type", "event_date", "locations")
    ordering = ("event_date", "start_time")
    filter_horizontal = ("locations",)
    fields = (
        "title",
        "event_type",
        "locations",
        "location",
        "event_date",
        "start_time",
        "end_time",
    )

    def display_locations(self, obj):
        return obj.location_names

    display_locations.short_description = "Locations"


@admin.register(PhaseOccupancy)
class PhaseOccupancyAdmin(admin.ModelAdmin):
    list_display = ("building", "time_phase", "expected_percentage")
    list_filter = ("time_phase", "building")


@admin.register(Path)
class PathAdmin(admin.ModelAdmin):
    list_display = ("from_building", "to_building", "distance")


@admin.register(EnergyConsumption)
class EnergyConsumptionAdmin(admin.ModelAdmin):
    list_display = ("year", "month", "scope", "building", "energy_consumed_kwh")
    list_filter = ("scope", "year", "month", "building")
    search_fields = ("building__name",)
    ordering = ("-year", "-month", "building__name")
    fields = (
        "scope",
        "building",
        "year",
        "month",
        "energy_consumed_kwh",
        "peak_demand_kw",
        "notes",
    )