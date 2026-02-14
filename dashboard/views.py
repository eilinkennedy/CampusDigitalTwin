from django.shortcuts import render
from django.utils import timezone
from datetime import time, date
from .models import Building, Event, PhaseOccupancy


# ---------------- HOME ----------------
def home(request):
    return render(request, "home_stitch.html")


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

    elif (
        time(10, 40) <= now < time(10, 55) or
        time(15, 0) <= now < time(15, 15)
    ):
        return "SHORT_BREAK"

    elif time(12, 35) <= now < time(13, 25):
        return "LUNCH_BREAK"

    elif time(16, 0) <= now < time(18, 0):
        return "ACTIVITIES"

    elif time(18, 0) <= now < time(19, 0):
        return "OFF_HOURS"

    elif now >= time(19, 0) or now < time(6, 0):
        return "NIGHT"

    return "OFF_HOURS"


# ---------------- DEFAULT REALISTIC RULES ----------------
def default_percentage(btype, phase):
    rules = {
        "ACADEMIC": {
            "CLASS_HOURS": 75,
            "SHORT_BREAK": 20,
            "LUNCH_BREAK": 20,
            "ACTIVITIES": 50,
            "OFF_HOURS": 0,
        },
        "LIBRARY": {
            "CLASS_HOURS": 60,
            "ACTIVITIES": 50,
            "OFF_HOURS": 10,
        },
        "ADMIN": {
            "CLASS_HOURS": 30,
            "OFF_HOURS": 0,
        },
        "CANTEEN": {
            "CLASS_HOURS": 5,
            "SHORT_BREAK": 70,
            "LUNCH_BREAK": 95,
            "ACTIVITIES": 60,
            "OFF_HOURS": 40,   # only till 6 PM
        },
        "HOSTEL": {
            "CLASS_HOURS": 20,
            "SHORT_BREAK": 20,
            "LUNCH_BREAK": 40,
            "ACTIVITIES": 50,
            "OFF_HOURS": 70,
            "NIGHT": 90,
        },
        "AUDITORIUM": {
            # event based
        },
    }

    return rules.get(btype, {}).get(phase, 0)


# ---------------- EFFECTIVE OCCUPANCY ----------------
def get_effective_occupancy(building, phase):
    cap = building.capacity
    now = timezone.localtime().time()

    # 🌙 NIGHT RULE
    if phase == "NIGHT":
        return int(0.9 * cap) if building.building_type == "HOSTEL" else 0

    # 🏟 AUDITORIUM — event based
    if building.building_type == "AUDITORIUM":
        has_event = Event.objects.filter(
            location__icontains=building.name,
            event_date=date.today()
        ).exists()
        return int(0.8 * cap) if has_event else 0

    # 🍽 CANTEEN closes after 6 PM
    if building.building_type == "CANTEEN" and now >= time(18, 0):
        return 0

    # 🔧 ADMIN-DEFINED PHASE OCCUPANCY (highest priority)
    phase_rule = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_rule:
        return int((phase_rule.expected_percentage / 100) * cap)

    # 🔁 FALLBACK DEFAULT RULES
    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * cap)


# ---------------- VISITOR PAGE ----------------
def visitor(request):
    phase = get_time_phase()
    buildings = Building.objects.all()
    grouped_buildings = {}

    for b in buildings:
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

        grouped_buildings.setdefault(b.building_type, []).append({
            "name": b.name,
            "status": status,
            "status_class": status_class
        })

    todays_events = Event.objects.filter(
        event_date=date.today()
    ).order_by("start_time")

    return render(request, "visitor_stitch.html", {
        "grouped_buildings": grouped_buildings,
        "todays_events": todays_events,
        "time_phase": phase
    })


# ---------------- ADMIN DASHBOARD ----------------
def admin_dashboard_stitch(request):
    phase = get_time_phase()
    buildings = Building.objects.all()

    for b in buildings:
        b.occupancy = get_effective_occupancy(b, phase)

        percent = int((b.occupancy / b.capacity) * 100) if b.capacity else 0

        # progress bar width
        if percent <= 10:
            b.width_class = "w-[10%]"
        elif percent <= 25:
            b.width_class = "w-1/4"
        elif percent <= 50:
            b.width_class = "w-1/2"
        elif percent <= 75:
            b.width_class = "w-3/4"
        else:
            b.width_class = "w-full"

        # status styles
        if percent == 0:
            b.status = "empty"
            b.bar_class = "bg-slate-300"
            b.badge_class = "bg-slate-200 text-slate-500"
        elif percent >= 80:
            b.status = "crowded"
            b.bar_class = "bg-red-500"
            b.badge_class = "bg-red-100 text-red-600"
        else:
            b.status = "normal"
            b.bar_class = "bg-primary"
            b.badge_class = "bg-primary/10 text-primary"

    return render(request, "dashboard_stitch.html", {
        "buildings": buildings,
        "time_phase": phase
    })
