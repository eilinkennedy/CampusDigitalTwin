import heapq
import json
from datetime import time

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    BuildingForm,
    EnergyConsumptionForm,
    EventForm,
    PathForm,
    PhaseOccupancyForm,
    StyledAuthenticationForm,
)
from .ml_models.data_loader import STUDY_LEAVE_MONTHS, load_energy_consumption_dataframe
from .ml_models.energy_predictor import predict_energy_for_years, predict_energy_per_building
from .models import Building, EnergyConsumption, Event, Path, PhaseOccupancy


def home(request):
    return render(request, "home_stitch.html")


class AdminLoginView(LoginView):
    template_name = "admin_login.html"
    authentication_form = StyledAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("admin_dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            logout(self.request)
            messages.error(self.request, "Only staff accounts can access the admin dashboard.")
            return redirect("admin_login")
        return response


def is_study_leave_date(target_date):
    return target_date.month in STUDY_LEAVE_MONTHS


# ---------------- TIME PHASE ----------------
def get_time_phase():
    now = timezone.localtime().time()

    if (
        time(9, 0) <= now < time(10, 40) or
        time(10, 55) <= now < time(12, 35) or
        time(13, 25) <= now < time(15, 0) or
        time(15, 15) <= now < time(16, 0)
    ):
        return "CLASS_HOURS"

    if (
        time(10, 40) <= now < time(10, 55) or
        time(15, 0) <= now < time(15, 15)
    ):
        return "SHORT_BREAK"

    if time(12, 35) <= now < time(13, 25):
        return "LUNCH_BREAK"

    if time(16, 0) <= now < time(18, 0):
        return "ACTIVITIES"

    return "OFF_HOURS"


# ---------------- DEFAULT OCCUPANCY ----------------
def default_percentage(building_type, phase):
    rules = {
        "ACADEMIC": {"CLASS_HOURS": 75, "SHORT_BREAK": 15, "LUNCH_BREAK": 10, "ACTIVITIES": 50, "OFF_HOURS": 0},
        "LIBRARY": {"CLASS_HOURS": 60, "ACTIVITIES": 50, "OFF_HOURS": 10},
        "ADMIN": {"CLASS_HOURS": 30, "OFF_HOURS": 0},
        "CANTEEN": {"SHORT_BREAK": 95, "LUNCH_BREAK": 95, "ACTIVITIES": 60, "OFF_HOURS": 0},
        "HOSTEL": {"CLASS_HOURS": 20, "SHORT_BREAK": 20, "LUNCH_BREAK": 40, "ACTIVITIES": 60, "OFF_HOURS": 90},
    }

    return rules.get(building_type, {}).get(phase, 0)


# ---------------- OCCUPANCY ENGINE ----------------
def get_effective_occupancy(building, phase):
    capacity = building.capacity

    if not capacity:
        return 0

    now = timezone.localtime()
    today = now.date()
    current_time = now.time()
    is_study_leave = is_study_leave_date(today)
    active_events = Event.objects.filter(
        event_date=today,
        start_time__lte=current_time,
        end_time__gte=current_time,
    ).distinct()
    exam_events = active_events.filter(event_type="EXAM")
    building_has_exam = exam_events.filter(
        Q(locations=building) | Q(location=building)
    ).exists()

    if building_has_exam and building.building_type == "ACADEMIC":
        return int(0.9 * capacity)

    if exam_events.exists():
        return int(0.05 * capacity)

    building_active_events = active_events.filter(
        Q(locations=building) | Q(location=building)
    ).distinct()

    if building_active_events.exists():
        return int(0.9 * capacity)

    if is_study_leave:
        if building.building_type == "HOSTEL":
            return int(0.05 * capacity)

        if building.building_type == "LIBRARY":
            return int(0.1 * capacity)

        if building.building_type == "ACADEMIC":
            return 0

    phase_entry = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase,
    ).first()

    if phase_entry:
        return int((phase_entry.expected_percentage / 100) * capacity)

    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * capacity)


# ---------------- DIJKSTRA ----------------
def dijkstra_shortest_path(start_building, end_building):
    graph = {}

    for p in Path.objects.all():
        graph.setdefault(p.from_building.id, []).append((p.to_building.id, p.distance))
        graph.setdefault(p.to_building.id, []).append((p.from_building.id, p.distance))

    queue = [(0, start_building.id)]
    distances = {start_building.id: 0}
    previous = {}

    while queue:
        current_distance, current_node = heapq.heappop(queue)

        if current_node == end_building.id:
            break

        for neighbor, weight in graph.get(current_node, []):
            new_distance = current_distance + weight

            if neighbor not in distances or new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                previous[neighbor] = current_node
                heapq.heappush(queue, (new_distance, neighbor))

    path_ids = []
    current = end_building.id

    while current in previous:
        path_ids.insert(0, current)
        current = previous[current]

    if path_ids:
        path_ids.insert(0, start_building.id)

    ordered_path = [Building.objects.get(id=i) for i in path_ids]
    return ordered_path, distances.get(end_building.id)


def build_route_steps(path):
    if len(path) < 2:
        return []

    building_ids = [building.id for building in path]
    path_lookup = {
        (segment.from_building_id, segment.to_building_id): segment
        for segment in Path.objects.filter(
            from_building_id__in=building_ids,
            to_building_id__in=building_ids,
        )
    }

    route_steps = []

    for index in range(len(path) - 1):
        current = path[index]
        next_building = path[index + 1]
        path_segment = path_lookup.get((current.id, next_building.id))

        if path_segment is None:
            path_segment = path_lookup.get((next_building.id, current.id))

        instruction = (
            path_segment.direction_hint
            if path_segment and path_segment.direction_hint
            else f"Move from {current.name} to {next_building.name}."
        )

        route_steps.append({
            "step_number": index + 1,
            "from": current.name,
            "to": next_building.name,
            "instruction": instruction,
        })

    return route_steps


def build_route_summary(path):
    route_steps = build_route_steps(path)
    if not route_steps:
        return ""

    summary_lines = []

    for index, step in enumerate(route_steps):
        summary_lines.append(f"{step['from']} -> {step['to']}")
        summary_lines.append(f"Instruction: {step['instruction']}")

        if index < len(route_steps) - 1:
            summary_lines.append("")

    return "\n".join(summary_lines)


def _build_route_steps(path):
    return build_route_steps(path)


def _build_occupancy_projection_payload(buildings):
    current_year = timezone.localdate().year
    total_current_occupancy = sum(b.occupancy for b in buildings)
    total_capacity = sum((b.capacity or 0) for b in buildings)

    years = []
    predicted = []
    increased_population = []

    normal_growth_rate = 0.03
    population_increase_rate = 0.06

    for step in range(1, 11):
        year = current_year + step
        normal_projection = total_current_occupancy * ((1 + normal_growth_rate) ** step)
        population_projection = total_current_occupancy * ((1 + population_increase_rate) ** step)

        if total_capacity:
            normal_projection = min(normal_projection, total_capacity)
            population_projection = min(population_projection, total_capacity)

        years.append(str(year))
        predicted.append(round(normal_projection, 2))
        increased_population.append(round(population_projection, 2))

    return {
        "current_year": current_year,
        "current_total_occupancy": total_current_occupancy,
        "current_total_capacity": total_capacity,
        "current_students": total_current_occupancy,
        "future_years": years,
        "predicted_occupancy": predicted,
        "population_increase_occupancy": increased_population,
    }


def _build_energy_payload():
    energy_df = load_energy_consumption_dataframe(scope="COLLEGE")

    if energy_df.empty:
        energy_df = load_energy_consumption_dataframe(scope="BUILDING")

    if energy_df.empty:
        return {
            "has_data": False,
            "historical_years": [],
            "historical_values": [],
            "predicted_years": [],
            "predicted_values": [],
            "model_name": "RandomForestRegressor",
            "building_predictions_year": None,
            "building_predictions": [],
            "total_campus_energy": 0.0,
            "heatmap_points": [],
        }

    annual_history = (
        energy_df.groupby("year", as_index=False)["energy_consumed_kwh"]
        .sum()
        .sort_values("year")
    )

    last_historical_year = int(annual_history["year"].max())
    future_predictions = predict_energy_for_years(
        start_year=last_historical_year + 1,
        years=10,
        building="College",
    )

    building_prediction_year = last_historical_year + 1
    building_prediction_payload = predict_energy_per_building(building_prediction_year)

    predicted_years = [str(item["year"]) for item in future_predictions if item["predicted_kwh"] is not None]
    predicted_values = [item["predicted_kwh"] for item in future_predictions if item["predicted_kwh"] is not None]

    heatmap_points = []
    for item in building_prediction_payload["building_predictions"]:
        if item.get("lat") is not None and item.get("lng") is not None:
            heatmap_points.append(
                {
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "energy": item["predicted_kwh"],
                    "building": item["building"],
                    "building_type": item["building_type"],
                    "study_leave_peak_kwh": item["study_leave_peak_kwh"],
                    "study_leave_alert": item["study_leave_alert"],
                    "study_leave_alert_reason": item["study_leave_alert_reason"],
                }
            )

    return {
        "has_data": True,
        "historical_years": [str(int(year)) for year in annual_history["year"].tolist()],
        "historical_values": [round(float(v), 2) for v in annual_history["energy_consumed_kwh"].tolist()],
        "predicted_years": predicted_years,
        "predicted_values": predicted_values,
        "model_name": "RandomForestRegressor",
        "building_predictions_year": building_prediction_year,
        "building_predictions": building_prediction_payload["building_predictions"],
        "total_campus_energy": building_prediction_payload["total_campus_energy"],
        "current_energy_demand": round(float(annual_history["energy_consumed_kwh"].iloc[-1]), 2),
        "heatmap_points": heatmap_points,
    }


def _build_operations_dashboard_context():
    phase = get_time_phase()

    buildings = list(Building.objects.filter(is_navigational_only=False))

    for b in buildings:
        occ = get_effective_occupancy(b, phase)
        percent = (occ / b.capacity) * 100 if b.capacity else 0

        if percent == 0:
            b.status = "Empty"
            b.badge_class = "bg-slate-200 text-slate-600"
            b.bar_class = "bg-slate-400"
        elif percent >= 80:
            b.status = "Crowded"
            b.badge_class = "bg-red-100 text-red-700"
            b.bar_class = "bg-red-500"
        else:
            b.status = "Normal"
            b.badge_class = "bg-green-100 text-green-700"
            b.bar_class = "bg-green-500"

        b.occupancy = occ
        b.occupancy_percent = round(percent, 1)

    active_events = Event.objects.filter(
        event_date=timezone.localdate(),
        start_time__lte=timezone.localtime().time(),
        end_time__gte=timezone.localtime().time(),
    ).prefetch_related("locations").distinct()

    occupancy_chart_data = {
        "labels": [b.name for b in buildings],
        "occupancy": [b.occupancy for b in buildings],
        "capacity": [b.capacity or 0 for b in buildings],
    }

    occupancy_projection = _build_occupancy_projection_payload(buildings)
    energy_payload = _build_energy_payload()
    building_energy_map = {
        item["building"]: item["predicted_kwh"]
        for item in energy_payload.get("building_predictions", [])
    }
    simulation_buildings = [
        {
            "name": b.name,
            "capacity": b.capacity or 0,
            "current_occupancy": b.occupancy,
            "current_occupancy_percent": round(b.occupancy_percent, 1),
            "status": b.status,
            "badge_class": b.badge_class,
            "bar_class": b.bar_class,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "predicted_energy": round(float(building_energy_map.get(b.name, 0)), 2),
        }
        for b in buildings
    ]

    return {
        "buildings": buildings,
        "time_phase": phase,
        "active_events": active_events,
        "occupancy_chart_data": occupancy_chart_data,
        "occupancy_projection": occupancy_projection,
        "energy_payload": energy_payload,
        "simulation_buildings": simulation_buildings,
    }


ADMIN_MODEL_CONFIG = {
    "building": {
        "model": Building,
        "form_class": BuildingForm,
        "title": "Building",
        "title_plural": "Buildings",
        "description": "Manage campus buildings, capacities, and navigation coordinates.",
        "fields": ["name", "building_type", "capacity", "is_navigational_only"],
    },
    "event": {
        "model": Event,
        "form_class": EventForm,
        "title": "Event",
        "title_plural": "Events",
        "description": "Maintain scheduled events and their assigned locations.",
        "fields": ["title", "event_type", "event_date", "start_time", "end_time"],
    },
    "phaseoccupancy": {
        "model": PhaseOccupancy,
        "form_class": PhaseOccupancyForm,
        "title": "Phase Occupancy",
        "title_plural": "Phase Occupancy",
        "description": "Tune occupancy percentages for each building and time phase.",
        "fields": ["building", "time_phase", "expected_percentage"],
    },
    "path": {
        "model": Path,
        "form_class": PathForm,
        "title": "Path",
        "title_plural": "Paths",
        "description": "Edit walking routes and direction hints used in navigation.",
        "fields": ["from_building", "to_building", "distance", "direction_hint"],
    },
    "energyconsumption": {
        "model": EnergyConsumption,
        "form_class": EnergyConsumptionForm,
        "title": "Energy Consumption",
        "title_plural": "Energy Consumption",
        "description": "Track campus and building-level energy records.",
        "fields": ["scope", "building", "year", "month", "energy_consumed_kwh"],
    },
}


def _ensure_staff_user(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('admin_login')}?next={request.path}")
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Only staff accounts can access this area.")
        return redirect("home")
    return None


def _get_admin_model_config(model_key):
    config = ADMIN_MODEL_CONFIG.get(model_key)
    if not config:
        raise Http404("Unknown admin model.")
    return config


def _render_admin_model_list(request, model_key, extra_context=None):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    config = _get_admin_model_config(model_key)
    queryset = config["model"].objects.all()

    if model_key == "building":
        queryset = queryset.order_by("name")
    elif model_key == "event":
        queryset = queryset.order_by("-event_date", "-start_time")
    elif model_key == "phaseoccupancy":
        queryset = queryset.select_related("building").order_by("building__name", "time_phase")
    elif model_key == "path":
        queryset = queryset.select_related("from_building", "to_building").order_by("from_building__name", "to_building__name")
    elif model_key == "energyconsumption":
        queryset = queryset.select_related("building").order_by("-year", "-month", "scope")

    context = {
        "page_title": config["title_plural"],
        "section_title": config["title_plural"],
        "section_description": config["description"],
        "model_key": model_key,
        "config": config,
        "rows": queryset,
        "columns": config["fields"],
    }
    if extra_context:
        context.update(extra_context)
    return render(request, "admin_model_list.html", context)


def _render_admin_model_form(request, model_key, pk=None):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    config = _get_admin_model_config(model_key)
    instance = get_object_or_404(config["model"], pk=pk) if pk is not None else None
    form = config["form_class"](request.POST or None, instance=instance)

    if request.method == "POST" and form.is_valid():
        form.save()
        action = "updated" if instance else "created"
        messages.success(request, f"{config['title']} {action} successfully.")
        return redirect("admin_model_list", model_key=model_key)

    return render(
        request,
        "admin_model_form.html",
        {
            "page_title": f"{'Edit' if instance else 'Add'} {config['title']}",
            "section_title": f"{'Edit' if instance else 'Add'} {config['title']}",
            "section_description": config["description"],
            "config": config,
            "model_key": model_key,
            "form": form,
            "object": instance,
        },
    )


def _render_admin_model_delete(request, model_key, pk):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    config = _get_admin_model_config(model_key)
    instance = get_object_or_404(config["model"], pk=pk)

    return render(
        request,
        "admin_confirm_delete.html",
        {
            "page_title": f"Delete {config['title']}",
            "section_title": f"Delete {config['title']}",
            "section_description": "This action updates live project data and cannot be undone automatically.",
            "config": config,
            "model_key": model_key,
            "object": instance,
        },
    )


def admin_dashboard(request):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    modules = [
        {
            "title": "Building Occupancy",
            "description": "Review building occupancy phase rules and update expected percentages for each time slot.",
            "icon": "groups",
            "href": reverse("admin_occupancy"),
            "count": PhaseOccupancy.objects.count(),
            "count_label": "occupancy rules",
        },
        {
            "title": "Energy Consumption",
            "description": "View and edit campus energy records without using the default Django admin interface.",
            "icon": "bolt",
            "href": reverse("admin_energy"),
            "count": EnergyConsumption.objects.count(),
            "count_label": "energy records",
        },
        {
            "title": "Manage Data",
            "description": "Open the full custom data management workspace for buildings, events, occupancy, paths, and energy.",
            "icon": "database",
            "href": reverse("admin_manage_data"),
            "count": sum(config["model"].objects.count() for config in ADMIN_MODEL_CONFIG.values()),
            "count_label": "managed rows",
        },
    ]

    return render(
        request,
        "admin_dashboard.html",
        {
            "page_title": "Admin Dashboard",
            "modules": modules,
        },
    )


def admin_manage_data(request):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    collections = []
    for key, config in ADMIN_MODEL_CONFIG.items():
        collections.append(
            {
                "key": key,
                "title": config["title_plural"],
                "description": config["description"],
                "count": config["model"].objects.count(),
                "href": reverse("admin_model_list", kwargs={"model_key": key}),
            }
        )

    return render(
        request,
        "admin_manage_data.html",
        {
            "page_title": "Manage Data",
            "collections": collections,
        },
    )


def admin_occupancy(request):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    context = _build_operations_dashboard_context()
    context.update(
        {
            "page_title": "Building Occupancy",
            "manage_href": reverse("admin_model_list", kwargs={"model_key": "phaseoccupancy"}),
        }
    )
    return render(request, "admin_occupancy_module.html", context)


def admin_energy(request):
    access_denied = _ensure_staff_user(request)
    if access_denied:
        return access_denied

    context = _build_operations_dashboard_context()
    context.update(
        {
            "page_title": "Energy Consumption",
            "manage_href": reverse("admin_model_list", kwargs={"model_key": "energyconsumption"}),
        }
    )
    return render(request, "admin_energy_module.html", context)


def admin_model_list(request, model_key):
    return _render_admin_model_list(request, model_key)


def admin_model_create(request, model_key):
    return _render_admin_model_form(request, model_key)


def admin_model_edit(request, model_key, pk):
    return _render_admin_model_form(request, model_key, pk=pk)


def admin_model_delete(request, model_key, pk):
    if request.method == "POST":
        access_denied = _ensure_staff_user(request)
        if access_denied:
            return access_denied

        config = _get_admin_model_config(model_key)
        instance = get_object_or_404(config["model"], pk=pk)
        instance.delete()
        messages.success(request, f"{config['title']} deleted successfully.")
        return redirect("admin_model_list", model_key=model_key)

    return _render_admin_model_delete(request, model_key, pk)


@require_POST
def admin_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")


# ---------------- ADMIN DASHBOARD ----------------
@login_required
def admin_dashboard_stitch(request):
    return redirect("admin_dashboard")


# ---------------- VISITOR PAGE ----------------
def visitor(request):
    phase = get_time_phase()

    all_buildings = Building.objects.all()
    facility_buildings = Building.objects.exclude(is_navigational_only=True)

    grouped = {}

    for b in facility_buildings:
        occ = get_effective_occupancy(b, phase)

        if occ == 0:
            status = "Closed"
            status_class = "bg-slate-200 text-slate-600"
        elif occ / b.capacity >= 0.6:
            status = "In Use"
            status_class = "bg-yellow-100 text-yellow-700"
        else:
            status = "Open"
            status_class = "bg-green-100 text-green-700"

        grouped.setdefault(b.building_type, []).append({
            "name": b.name,
            "status": status,
            "status_class": status_class,
        })

    todays_events = Event.objects.filter(
        event_date=timezone.localdate(),
        start_time__lte=timezone.localtime().time(),
        end_time__gte=timezone.localtime().time(),
    ).prefetch_related("locations").distinct()

    selected_start = request.GET.get("start")
    selected_end = request.GET.get("end")

    return render(request, "visitor_stitch.html", {
        "grouped_buildings": grouped,
        "buildings": all_buildings,
        "todays_events": todays_events,
        "selected_start": selected_start,
        "selected_end": selected_end,
    })


# ---------------- NAVIGATION PAGE ----------------
def navigation(request):
    start_id = request.GET.get("start")
    end_id = request.GET.get("end")

    route_coords = []
    route_buildings = []
    total_distance = None
    route_summary = ""
    route_steps = []

    if start_id and end_id:
        start = Building.objects.get(id=start_id)
        end = Building.objects.get(id=end_id)

        path, total_distance = dijkstra_shortest_path(start, end)
        route_steps = build_route_steps(path)
        route_summary = build_route_summary(path)

        for b in path:
            if b.latitude is not None and b.longitude is not None:
                route_coords.append({"lat": b.latitude, "lng": b.longitude})
                route_buildings.append(b.name)

    campus_paths = []

    for p in Path.objects.all():
        if (
            p.from_building.latitude is not None and
            p.from_building.longitude is not None and
            p.to_building.latitude is not None and
            p.to_building.longitude is not None
        ):
            campus_paths.append({
                "coords": [
                    {"lat": p.from_building.latitude, "lng": p.from_building.longitude},
                    {"lat": p.to_building.latitude, "lng": p.to_building.longitude},
                ]
            })

    heatmap_year = timezone.localdate().year + 1
    heatmap_predictions = predict_energy_per_building(heatmap_year)
    building_energy_lookup = {
        item["building"]: item["predicted_kwh"]
        for item in heatmap_predictions["building_predictions"]
    }
    buildings_data = []
    phase = get_time_phase()
    for b in Building.objects.all():
        if b.latitude is not None and b.longitude is not None:
            current_occupancy = get_effective_occupancy(b, phase)
            capacity = b.capacity or 0
            occupancy_percent = round((current_occupancy / capacity) * 100, 1) if capacity else 0
            buildings_data.append({
                "name": b.name,
                "lat": b.latitude,
                "lng": b.longitude,
                "current_occupancy": current_occupancy,
                "capacity": capacity,
                "occupancy_percent": occupancy_percent,
                "predicted_energy": round(float(building_energy_lookup.get(b.name, 0)), 2),
            })

    energy_heatmap_data = []
    for item in heatmap_predictions["building_predictions"]:
        if item.get("lat") is not None and item.get("lng") is not None:
            energy_heatmap_data.append(
                {
                    "lat": item["lat"],
                    "lng": item["lng"],
                    "building": item["building"],
                    "building_type": item["building_type"],
                    "energy": item["predicted_kwh"],
                    "study_leave_peak_kwh": item["study_leave_peak_kwh"],
                    "study_leave_alert": item["study_leave_alert"],
                    "study_leave_alert_reason": item["study_leave_alert_reason"],
                }
            )

    return render(request, "navigation.html", {
        "route_coords": json.dumps(route_coords),
        "campus_paths": json.dumps(campus_paths),
        "buildings_data": json.dumps(buildings_data),
        "energy_heatmap_data": json.dumps(energy_heatmap_data),
        "heatmap_year": heatmap_year,
        "route_buildings": route_buildings,
        "route_steps": route_steps,
        "route_summary": route_summary,
        "total_distance": total_distance,
    })