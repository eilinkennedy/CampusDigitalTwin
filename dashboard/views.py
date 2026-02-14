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

    elif time(16, 0) <= now < time(16, 30):
        return "ACTIVITIES"

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
        },
        "LAB": {
            "CLASS_HOURS": 85,
            "ACTIVITIES": 40,
        },
        "LIBRARY": {
            "CLASS_HOURS": 60,
            "ACTIVITIES": 50,
        },
        "ADMIN": {
            "CLASS_HOURS": 30,   # LOW (as you wanted)
        },
        "CANTEEN": {
            "CLASS_HOURS": 5,
            "SHORT_BREAK": 70,
            "LUNCH_BREAK": 95,
            "ACTIVITIES": 60,
        },
        "HOSTEL": {
            "CLASS_HOURS": 20,   # ✅ LOW
            "SHORT_BREAK": 20,   # ✅ LOW
            "LUNCH_BREAK": 40,
            "ACTIVITIES": 50,
            "NIGHT": 90,
        },
        "SHOP": {
            "CLASS_HOURS": 40,
            "SHORT_BREAK": 60,
            "LUNCH_BREAK": 70,
            "ACTIVITIES": 60,
        },
        "AUDITORIUM": {
            # handled via events
        },
    }

    return rules.get(btype, {}).get(phase, 0)

# ---------------- EFFECTIVE OCCUPANCY ----------------
def get_effective_occupancy(building, phase):
    cap = building.capacity

    # 1️⃣ Phase-based admin configuration (HIGHEST PRIORITY)
    phase_rule = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_rule:
        return int((phase_rule.expected_percentage / 100) * cap)

    # 2️⃣ Auditorium → event based
    if building.building_type == "AUDITORIUM":
        has_event = Event.objects.filter(
            location__icontains=building.name,
            event_date=date.today()
        ).exists()
        return int(0.8 * cap) if has_event else 0

    # 3️⃣ Night rule
    if phase == "NIGHT":
        return int(0.9 * cap) if building.building_type == "HOSTEL" else 0

    # 4️⃣ Fallback defaults
    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * cap)

# ---------------- VISITOR ----------------
def visitor(request):
    phase = get_time_phase()
    buildings = Building.objects.all()
    grouped = {}

    for b in buildings:
        occ = get_effective_occupancy(b, phase)

        if occ == 0:
            status, cls = "Closed", "bg-slate-200 text-slate-600"
        elif occ / b.capacity >= 0.6:
            status, cls = "In Use", "bg-yellow-100 text-yellow-700"
        else:
            status, cls = "Open", "bg-green-100 text-green-700"

        grouped.setdefault(b.building_type, []).append({
            "name": b.name,
            "status": status,
            "status_class": cls
        })

    todays_events = Event.objects.filter(
        event_date=date.today()
    ).order_by("start_time")

    return render(request, "visitor_stitch.html", {
        "grouped_buildings": grouped,
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

        b.width_class = (
            "w-[10%]" if percent <= 10 else
            "w-1/4" if percent <= 25 else
            "w-1/2" if percent <= 50 else
            "w-3/4" if percent <= 75 else
            "w-full"
        )

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
