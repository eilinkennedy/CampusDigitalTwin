'''from django.shortcuts import render
from django.utils import timezone
from datetime import time, date
from django.contrib.auth.decorators import login_required
from .models import Building, Event, PhaseOccupancy

# ================= HOME =================
def home(request):
    return render(request, "home_stitch.html")

# ================= TIME PHASE LOGIC =================
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

    elif now >= time(18, 0) or now < time(6, 0):
        return "OFF_HOURS"

    return "OFF_HOURS"

# ================= DEFAULT FALLBACK RULES =================
def default_percentage(building_type, phase):
    rules = {
        "ACADEMIC": {
            "CLASS_HOURS": 75,
            "SHORT_BREAK": 15,
            "LUNCH_BREAK": 10,
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
            "SHORT_BREAK": 70,
            "LUNCH_BREAK": 95,
            "ACTIVITIES": 60,
            "OFF_HOURS": 0,
        },
        "HOSTEL": {
            "CLASS_HOURS": 20,
            "SHORT_BREAK": 20,
            "LUNCH_BREAK": 40,
            "ACTIVITIES": 60,
            "OFF_HOURS": 90,
        },
        "AUDITORIUM": {}
    }

    return rules.get(building_type, {}).get(phase, 0)

# ================= EFFECTIVE OCCUPANCY =================
def get_effective_occupancy(building, phase):
    capacity = building.capacity

    if building.building_type == "AUDITORIUM":
        now = timezone.localtime()
        has_active_event = Event.objects.filter(
            location__icontains=building.name,
            event_date=date.today(),
            start_time__lte=now.time(),
            end_time__gte=now.time()
        ).exists()

        return int(0.8 * capacity) if has_active_event else 0

    phase_entry = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_entry:
        return int((phase_entry.expected_percentage / 100) * capacity)

    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * capacity)

# ================= VISITOR PAGE =================
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

    now = timezone.localtime()
    todays_events = Event.objects.filter(
        event_date=now.date(),
        end_time__gt=now.time()
    ).order_by("start_time")

    return render(request, "visitor_stitch.html", {
        "grouped_buildings": grouped,
        "todays_events": todays_events,
        "time_phase": phase
    })

# ================= ADMIN DASHBOARD (PROTECTED) =================
@login_required(login_url='/admin/login/')
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
            b.border_class = "border-slate-200"
            b.text_class = "text-slate-500"

        elif percent >= 80:
            b.status = "crowded"
            b.bar_class = "bg-red-500"
            b.badge_class = "bg-red-100 text-red-600"
            b.border_class = "border-red-500/30"
            b.text_class = "text-red-600"

        else:
            b.status = "normal"
            b.bar_class = "bg-primary"
            b.badge_class = "bg-primary/10 text-primary"
            b.border_class = "border-slate-100"
            b.text_class = "text-slate-500"

    return render(request, "dashboard_stitch.html", {
        "buildings": buildings,
        "time_phase": phase
    })'''
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import time
from .models import Building, Event, PhaseOccupancy


# ================= HOME =================
def home(request):
    return render(request, "home_stitch.html")


# ================= TIME PHASE LOGIC =================
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

    else:
        return "OFF_HOURS"


# ================= DEFAULT RULES =================
def default_percentage(building_type, phase):
    rules = {
        "ACADEMIC": {
            "CLASS_HOURS": 75,
            "SHORT_BREAK": 15,
            "LUNCH_BREAK": 10,
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
            "SHORT_BREAK": 95,
            "LUNCH_BREAK": 95,
            "ACTIVITIES": 60,
            "OFF_HOURS": 0,
        },
        "HOSTEL": {
            "CLASS_HOURS": 20,
            "SHORT_BREAK": 20,
            "LUNCH_BREAK": 40,
            "ACTIVITIES": 60,
            "OFF_HOURS": 90,
        },
    }

    return rules.get(building_type, {}).get(phase, 0)


# ================= CORE OCCUPANCY LOGIC =================
def get_effective_occupancy(building, phase):
    capacity = building.capacity
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()

    # ---- Detect today's exam ----
    todays_exams = Event.objects.filter(
        event_date=today,
        event_type="EXAM"
    )

    active_exam = False
    exam_ended_recently = False

    for exam in todays_exams:
        if exam.start_time <= current_time <= exam.end_time:
            active_exam = True
        elif current_time > exam.end_time:
            exam_ended_recently = True

    # ---- DURING EXAM ----
    if active_exam:
        if building.building_type == "ACADEMIC":
            return int(0.9 * capacity)
        elif building.building_type == "HOSTEL":
            return int(0.05 * capacity)
        elif building.building_type == "CANTEEN":
            return int(0.1 * capacity)
        elif building.building_type == "LIBRARY":
            return int(0.1 * capacity)  # LOW during exam

    # ---- AFTER EXAM (Library Surge) ----
    if exam_ended_recently and building.building_type == "LIBRARY":
        return int(0.85 * capacity)  # Crowded after exam

    # ---- AUDITORIUM LOGIC ----
    if building.building_type == "AUDITORIUM":
        todays_events = Event.objects.filter(
            location=building,
            event_date=today
        )
        for event in todays_events:
            if event.start_time <= current_time <= event.end_time:
                return int(0.8 * capacity)
        return 0

    # ---- PHASE OCCUPANCY ----
    phase_entry = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_entry:
        return int((phase_entry.expected_percentage / 100) * capacity)

    # ---- DEFAULT RULE ----
    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * capacity)

    # ---- PHASE OCCUPANCY (Admin Defined) ----
    phase_entry = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_entry:
        return int((phase_entry.expected_percentage / 100) * capacity)

    # ---- DEFAULT RULES ----
    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * capacity)
    # ===== PHASE OCCUPANCY FROM ADMIN =====
    phase_entry = PhaseOccupancy.objects.filter(
        building=building,
        time_phase=phase
    ).first()

    if phase_entry:
        return int((phase_entry.expected_percentage / 100) * capacity)

    # ===== FALLBACK =====
    percentage = default_percentage(building.building_type, phase)
    return int((percentage / 100) * capacity)


# ================= VISITOR PAGE =================
def visitor(request):
    phase = get_time_phase()
    buildings = Building.objects.all()
    grouped = {}

    now = timezone.localtime()
    today = now.date()
    current_time = now.time()

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

        grouped.setdefault(b.building_type, []).append({
            "name": b.name,
            "status": status,
            "status_class": status_class,
        })

    todays_events = Event.objects.filter(
        event_date=today,
        start_time__lte=current_time,
        end_time__gte=current_time,
    ).order_by("start_time")

    return render(request, "visitor_stitch.html", {
        "grouped_buildings": grouped,
        "todays_events": todays_events,
        "time_phase": phase,
    })


# ================= ADMIN DASHBOARD =================
@login_required
def admin_dashboard_stitch(request):
    phase = get_time_phase()
    buildings = Building.objects.all()

    from django.utils import timezone
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()

    # Get today's events
    todays_events = Event.objects.filter(event_date=today)

    # Manually detect active events
    active_events = []
    for event in todays_events:
        if event.start_time <= current_time <= event.end_time:
            active_events.append(event)

    # Calculate occupancy for each building
    for b in buildings:
        b.occupancy = get_effective_occupancy(b, phase)

        percent = int((b.occupancy / b.capacity) * 100) if b.capacity else 0

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
        "time_phase": phase,
        "active_events": active_events,
    })