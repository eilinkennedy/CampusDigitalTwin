from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .ml_models.data_loader import (
    BASELINE_CAMPUS_POPULATION,
    BUILDING_ENERGY_MULTIPLIERS,
    load_energy_consumption_dataframe,
)
from .ml_models.energy_predictor import _build_prediction_frame, predict_energy_per_building
from .models import Building, EnergyConsumption, Event, Path, PhaseOccupancy
from .views import build_route_steps, build_route_summary, get_effective_occupancy


class NavigationViewTests(TestCase):
    def setUp(self):
        self.a = Building.objects.create(name="A", latitude=0, longitude=0)
        self.b = Building.objects.create(name="B", latitude=0, longitude=1)
        self.c = Building.objects.create(name="C", latitude=1, longitude=1)
        Path.objects.create(from_building=self.a, to_building=self.b, distance=1, direction_hint="A to B")
        Path.objects.create(from_building=self.b, to_building=self.c, distance=1, direction_hint="B to C")

    def test_route_computation(self):
        url = reverse("navigation")
        response = self.client.get(url, {"start": self.a.id, "end": self.c.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("route_coords", response.context)
        self.assertIn("campus_paths", response.context)
        self.assertIn('"lat"', response.context["route_coords"])
        self.assertIn('"lat"', response.context["campus_paths"])

    def test_build_route_summary_uses_direction_hints(self):
        summary = build_route_summary([self.a, self.b, self.c])

        self.assertIn("A -> B", summary)
        self.assertIn("Instruction: A to B", summary)
        self.assertIn("B -> C", summary)
        self.assertIn("Instruction: B to C", summary)

    def test_build_route_steps_returns_structured_hops(self):
        steps = build_route_steps([self.a, self.b, self.c])

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["from"], "A")
        self.assertEqual(steps[0]["to"], "B")
        self.assertEqual(steps[0]["instruction"], "A to B")


class StudyLeaveOccupancyTests(TestCase):
    def setUp(self):
        self.hostel = Building.objects.create(name="Hostel", building_type="HOSTEL", capacity=200)
        self.library = Building.objects.create(name="Library", building_type="LIBRARY", capacity=100)
        self.academic = Building.objects.create(name="Block A", building_type="ACADEMIC", capacity=300)

    def test_study_leave_default_overrides(self):
        mocked_now = timezone.make_aware(datetime(2026, 4, 10, 11, 0))

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.hostel, "CLASS_HOURS"), 10)
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 10)
            self.assertEqual(get_effective_occupancy(self.academic, "CLASS_HOURS"), 0)

    def test_exam_event_restores_academic_exam_load(self):
        mocked_now = timezone.make_aware(datetime(2026, 4, 10, 11, 0))
        event = Event.objects.create(
            title="Semester Exam",
            event_type="EXAM",
            location=self.academic,
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.academic)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.academic, "CLASS_HOURS"), 270)
            self.assertEqual(get_effective_occupancy(self.hostel, "CLASS_HOURS"), 10)
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 5)

    def test_general_event_makes_event_location_crowded(self):
        mocked_now = timezone.make_aware(datetime(2026, 7, 15, 11, 0))
        event = Event.objects.create(
            title="Admission Help Desk",
            event_type="ADMISSION",
            location=self.library,
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.library)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 90)

    def test_event_override_applies_before_normal_phase_occupancy(self):
        mocked_now = timezone.make_aware(datetime(2026, 7, 15, 11, 0))
        PhaseOccupancy.objects.create(
            building=self.library,
            time_phase="CLASS_HOURS",
            expected_percentage=30,
        )
        event = Event.objects.create(
            title="Parent Meeting",
            event_type="PTA",
            location=self.library,
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.library)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 90)

    def test_non_exam_events_only_crowd_selected_location(self):
        mocked_now = timezone.make_aware(datetime(2026, 7, 15, 11, 0))
        PhaseOccupancy.objects.create(
            building=self.hostel,
            time_phase="CLASS_HOURS",
            expected_percentage=40,
        )
        PhaseOccupancy.objects.create(
            building=self.academic,
            time_phase="CLASS_HOURS",
            expected_percentage=55,
        )
        event = Event.objects.create(
            title="Placement Drive",
            event_type="PLACEMENT",
            location=self.library,
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.library)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 90)
            self.assertEqual(get_effective_occupancy(self.hostel, "CLASS_HOURS"), 80)
            self.assertEqual(get_effective_occupancy(self.academic, "CLASS_HOURS"), 165)

    def test_multi_location_event_marks_each_selected_building_crowded(self):
        mocked_now = timezone.make_aware(datetime(2026, 7, 15, 11, 0))
        event = Event.objects.create(
            title="Central Admission",
            event_type="ADMISSION",
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.library, self.academic)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 90)
            self.assertEqual(get_effective_occupancy(self.academic, "CLASS_HOURS"), 270)

    def test_multi_location_exam_only_exam_blocks_are_crowded(self):
        mocked_now = timezone.make_aware(datetime(2026, 4, 10, 11, 0))
        second_academic = Building.objects.create(
            name="Block B",
            building_type="ACADEMIC",
            capacity=250,
        )
        event = Event.objects.create(
            title="University Exam",
            event_type="EXAM",
            event_date=mocked_now.date(),
            start_time=mocked_now.time().replace(minute=0),
            end_time=mocked_now.time().replace(hour=12, minute=0),
        )
        event.locations.add(self.academic, second_academic)

        with patch("dashboard.views.timezone.localtime", return_value=mocked_now):
            self.assertEqual(get_effective_occupancy(self.academic, "CLASS_HOURS"), 270)
            self.assertEqual(get_effective_occupancy(second_academic, "CLASS_HOURS"), 225)
            self.assertEqual(get_effective_occupancy(self.hostel, "CLASS_HOURS"), 10)
            self.assertEqual(get_effective_occupancy(self.library, "CLASS_HOURS"), 5)


class EnergyFeatureTests(TestCase):
    def setUp(self):
        self.hostel = Building.objects.create(name="Hostel", building_type="HOSTEL", capacity=200)
        self.library = Building.objects.create(name="Library", building_type="LIBRARY", capacity=100)
        EnergyConsumption.objects.create(
            scope="BUILDING",
            building=self.hostel,
            year=2025,
            month=4,
            energy_consumed_kwh=1200,
        )
        EnergyConsumption.objects.create(
            scope="BUILDING",
            building=self.library,
            year=2025,
            month=7,
            energy_consumed_kwh=800,
        )

    def test_data_loader_marks_feature_months(self):
        df = load_energy_consumption_dataframe(scope="BUILDING")

        april_row = df[(df["year"] == 2025) & (df["month"] == 4)].iloc[0]
        july_row = df[(df["year"] == 2025) & (df["month"] == 7)].iloc[0]
        march_frame = _build_prediction_frame(2027, self.hostel.name)

        self.assertEqual(april_row["is_exam_month"], 1)
        self.assertEqual(april_row["is_study_leave"], 1)
        self.assertEqual(april_row["is_peak_summer"], 1)
        self.assertEqual(july_row["is_study_leave"], 0)
        self.assertEqual(july_row["is_peak_summer"], 0)
        self.assertEqual(april_row["campus_population"], BASELINE_CAMPUS_POPULATION)
        self.assertEqual(march_frame.loc[march_frame["month"] == 3, "is_peak_summer"].iloc[0], 1)

    def test_prediction_frame_includes_new_features(self):
        frame = _build_prediction_frame(2027, self.hostel.name)

        self.assertIn("is_study_leave", frame.columns)
        self.assertIn("is_peak_summer", frame.columns)
        self.assertEqual(frame.loc[frame["month"] == 4, "is_exam_month"].iloc[0], 1)
        self.assertEqual(frame.loc[frame["month"] == 4, "is_study_leave"].iloc[0], 1)
        self.assertEqual(frame.loc[frame["month"] == 6, "is_study_leave"].iloc[0], 0)
        self.assertEqual(frame.loc[frame["month"] == 5, "is_peak_summer"].iloc[0], 1)
        self.assertEqual(frame.loc[frame["month"] == 7, "is_peak_summer"].iloc[0], 0)

    def test_synthetic_rows_include_noise_and_calendar_adjustments(self):
        df = load_energy_consumption_dataframe(scope="BUILDING")

        synthetic_april = df[
            (df["year"] == 2024) &
            (df["month"] == 4) &
            (df["building"] == "Hostel")
        ].iloc[0]
        synthetic_july = df[
            (df["year"] == 2024) &
            (df["month"] == 7) &
            (df["building"] == "Library")
        ].iloc[0]

        april_without_noise = 1200 * 0.95 * BUILDING_ENERGY_MULTIPLIERS["HOSTEL"] * 1.15 * 0.75 * 0.60
        july_without_noise = 800 * 0.95 * BUILDING_ENERGY_MULTIPLIERS["LIBRARY"]

        self.assertNotAlmostEqual(synthetic_april["energy_consumed_kwh"], april_without_noise, places=6)
        self.assertNotAlmostEqual(synthetic_july["energy_consumed_kwh"], july_without_noise, places=6)


class HeatmapAlertTests(TestCase):
    def setUp(self):
        self.hostel = Building.objects.create(name="Hostel", building_type="HOSTEL", capacity=200)
        self.academic = Building.objects.create(name="Block A", building_type="ACADEMIC", capacity=300)

    @patch("dashboard.ml_models.energy_predictor.load_or_train_model", return_value={"model": object()})
    @patch("dashboard.ml_models.energy_predictor._predict_with_payload")
    def test_study_leave_alerts_flag_high_hostel_loads(self, predict_mock, _load_model_mock):
        def fake_predict(_payload, _year, building_name, _campus_population, month=None):
            if month in {4, 5} and building_name == "Hostel":
                return 500.0
            if month in {4, 5} and building_name == "Block A":
                return 50.0
            return 1000.0

        predict_mock.side_effect = fake_predict

        payload = predict_energy_per_building(2027)
        building_predictions = {item["building"]: item for item in payload["building_predictions"]}

        self.assertTrue(building_predictions["Hostel"]["study_leave_alert"])
        self.assertFalse(building_predictions["Block A"]["study_leave_alert"])


class CustomAdminTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.staff_user = self.user_model.objects.create_user(
            username="adminuser",
            password="testpass123",
            is_staff=True,
        )
        self.regular_user = self.user_model.objects.create_user(
            username="regularuser",
            password="testpass123",
        )
        self.building = Building.objects.create(name="Admin Block", building_type="ADMIN", capacity=50)

    def test_home_secure_login_points_to_custom_login(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("admin_login"))
        self.assertNotContains(response, 'href="/admin/"')
        self.assertNotContains(response, "Enter Dashboard")
        self.assertNotContains(response, "Campus Overview")

    def test_custom_admin_login_redirects_staff_to_dashboard(self):
        response = self.client.post(
            reverse("admin_login"),
            {"username": "adminuser", "password": "testpass123"},
        )

        self.assertRedirects(response, reverse("admin_dashboard"))

    def test_custom_admin_login_rejects_non_staff_users(self):
        response = self.client.post(
            reverse("admin_login"),
            {"username": "regularuser", "password": "testpass123"},
            follow=True,
        )

        self.assertContains(response, "Only staff accounts can access the admin dashboard.")

    def test_manage_data_page_requires_staff_access(self):
        response = self.client.get(reverse("admin_manage_data"))

        self.assertRedirects(response, f"{reverse('admin_login')}?next={reverse('admin_manage_data')}")

    def test_staff_can_create_energy_record_from_custom_admin(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("admin_model_create", kwargs={"model_key": "energyconsumption"}),
            {
                "scope": "BUILDING",
                "building": self.building.id,
                "year": 2026,
                "month": 2,
                "energy_consumed_kwh": 1234.5,
                "peak_demand_kw": 54.2,
                "notes": "Seeded from custom admin",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin_model_list", kwargs={"model_key": "energyconsumption"}),
        )
        self.assertTrue(
            EnergyConsumption.objects.filter(
                building=self.building,
                year=2026,
                month=2,
                energy_consumed_kwh=1234.5,
            ).exists()
        )

    def test_occupancy_module_shows_dashboard_content(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin_occupancy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Building Occupancy")
        self.assertContains(response, "Current Total Occupancy")
        self.assertContains(response, "Manage Occupancy Data")

    def test_energy_module_shows_dashboard_content(self):
        EnergyConsumption.objects.create(
            scope="BUILDING",
            building=self.building,
            year=2025,
            month=1,
            energy_consumed_kwh=400,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin_energy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Energy Consumption")
        self.assertContains(response, "Current Energy Demand")
        self.assertContains(response, "Manage Energy Data")

    def test_legacy_dashboard_route_redirects_to_admin_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("dashboard_ui"))

        self.assertRedirects(response, reverse("admin_dashboard"))