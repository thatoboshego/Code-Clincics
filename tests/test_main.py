import unittest
from unittest.mock import patch, MagicMock
import datetime
from datetime import date

# booking imports
from booking import (
    normalize_slot,
    resolve_slot,
    is_volunteer_assigned,
    is_student_booked,
    book_slot,
    volunteer_slot
)

# calendar_sync imports
from calendar_sync import CalendarService

# cancel imports
from cancel import cancel_student_booking, cancel_volunteer_booking

# clinic imports
from clinic import normalize_slot as clinic_normalize_slot, require_role, divider, next_step

# scheduler imports
from scheduler import (
    get_slot_display_status,
    is_slot_available_for_role,
    display_summary,
    view_day
)


# Booking Helper Tests

class TestBookingHelpers(unittest.TestCase):

    def test_normalize_slot_hour_format(self):
        result = normalize_slot("2026-06-10_14")
        self.assertEqual(result, "2026-06-10_14:00")

    def test_normalize_slot_full_format(self):
        result = normalize_slot("2026-06-10_14:30")
        self.assertEqual(result, "2026-06-10_14:30")

    def test_resolve_slot_found(self):
        slots = {
            "2026-06-10_14:00": {"volunteer": "vol@test.com"}
        }
        key, slot = resolve_slot("2026-06-10_14", slots)
       
        self.assertIsNotNone(slot)
        self.assertIsNotNone(key)
        if slot is not None:
            self.assertEqual(slot["volunteer"], "vol@test.com")
    
    def test_resolve_slot_not_found(self):
        slots = {}
        key, slot = resolve_slot("2026-06-10_14", slots)
        self.assertIsNone(key)
        self.assertIsNone(slot)


# Slot Check Tests

class TestSlotChecks(unittest.TestCase):

    def test_is_volunteer_assigned_true(self):
        state = {"slots": {"2026-06-10_14:00": {"volunteer": "vol@test.com"}}}
        result = is_volunteer_assigned("2026-06-10_14:00", state)
        self.assertTrue(result)

    def test_is_student_booked_true(self):
        state = {"slots": {"2026-06-10_14:00": {"student": "student@test.com"}}}
        result = is_student_booked("2026-06-10_14:00", state)
        self.assertTrue(result)


# Booking Action Tests

class TestBookingActions(unittest.TestCase):

    @patch("booking.CalendarService")
    @patch("booking.send_booking_emails")
    def test_book_slot_success(self, mock_email, mock_service_class):
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        state = {
            "slots": {
                "2026-06-10_14:00": {
                    "volunteer": "vol@test.com",
                    "student": None,
                    "status": "volunteer_assigned",
                    "event_ids": {"personal": ["existing_event_id"], "clinic": []}
                }
            },
            "volunteers": {"vol@test.com": {"name": "Alice"}}
        }

        mock_service.load_state.return_value = state
        mock_service.add_event_to_calendar.side_effect = ["p1", "c1"]

        book_slot("Lebo", "student@test.com", "2026-06-10_14:00", "Need help with Python")

        slot = state["slots"]["2026-06-10_14:00"]
        self.assertEqual(slot["student"], "student@test.com")
        self.assertEqual(slot["status"], "confirmed")
        self.assertIn("student@test.com", state["students"])

    @patch("booking.CalendarService")
    def test_volunteer_slot_success(self, mock_service_class):
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        state = {
            "slots": {
                "2026-06-10_14:00": {
                    "volunteer": None,
                    "status": "empty",
                    "event_ids": {"personal": [], "clinic": []}
                }
            }
        }

        mock_service.load_state.return_value = state
        mock_service.add_event_to_calendar.side_effect = ["p1", "c1"]

        volunteer_slot("Alice", "vol@test.com", "2026-06-10_14:00")

        slot = state["slots"]["2026-06-10_14:00"]
        self.assertEqual(slot["volunteer"], "vol@test.com")
        self.assertEqual(slot["status"], "volunteer_assigned")
        self.assertIn("vol@test.com", state["volunteers"])


# Calendar Service Tests

class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2025, 1, 1, tzinfo=tz)


class TestCalendarService(unittest.TestCase):

    def setUp(self):
        patcher = patch("calendar_sync.authenticate_google", return_value=MagicMock())
        self.addCleanup(patcher.stop)
        patcher.start()
        self.service = CalendarService("TestUser", "admin@test.com")

    @patch("calendar_sync.datetime.datetime", FixedDateTime)
    def test_clear_old_data_removes_past_slots(self):
        state = {
            "slots": {"2024-12-31_09:00_JHB": {}, "2025-01-01_09:00_JHB": {}},
            "students": {},
            "volunteers": {},
            "admin_logs": [],
            "last_synced": None
        }
        cleaned = self.service.clear_old_data(state)
        self.assertNotIn("2024-12-31_09:00_JHB", cleaned["slots"])
        self.assertIn("2025-01-01_09:00_JHB", cleaned["slots"])

    @patch("calendar_sync.datetime.datetime", FixedDateTime)
    @patch.object(CalendarService, "save_state")
    @patch.object(CalendarService, "load_state")
    def test_start_sync_creates_slots(self, mock_load, mock_save):
        mock_load.return_value = {"slots": {}, "students": {}, "volunteers": {}, "admin_logs": [], "last_synced": None}
        self.service.start_sync("JHB")
        mock_save.assert_called()
        saved_state = mock_save.call_args[0][0]
        self.assertTrue(len(saved_state["slots"]) > 0)
        self.assertEqual(saved_state["last_synced"], "2025-01-01")

    @patch.object(CalendarService, "save_state")
    @patch.object(CalendarService, "load_state")
    def test_log_admin_action(self, mock_load, mock_save):
        mock_load.return_value = {"slots": {}, "students": {}, "volunteers": {}, "admin_logs": [], "last_synced": None}
        self.service.log_admin_action("cancel", "2025-01-01_09:00_JHB", "student@test.com", "vol@test.com")
        mock_save.assert_called()
        updated_state = mock_save.call_args[0][0]
        self.assertEqual(len(updated_state["admin_logs"]), 1)
        self.assertEqual(updated_state["admin_logs"][0]["action"], "cancel")


# Cancel Tests

class TestCancelFunctions(unittest.TestCase):

    @patch("cancel.CalendarService")
    def test_cancel_student_booking_success(self, mock_service_class):
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        state = {
            "slots": {"slot1": {"student": "student@test.com", "volunteer": "vol@test.com", "status": "booked", "event_ids": {"personal": [], "clinic": []}}},
            "students": {"student@test.com": {"booked_slots": ["slot1"]}}
        }
        mock_service.load_state.return_value = state
        with patch("cancel.resolve_slot", return_value=("slot1", state["slots"]["slot1"])):
            cancel_student_booking("Student", "student@test.com", "slot1")
        self.assertIsNone(state["slots"]["slot1"]["student"])
        self.assertEqual(state["slots"]["slot1"]["status"], "volunteer_assigned")
        self.assertEqual(state["students"]["student@test.com"]["booked_slots"], [])

    @patch("cancel.CalendarService")
    def test_cancel_volunteer_booking_success(self, mock_service_class):
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        state = {
            "slots": {"slot1": {"student": None, "volunteer": "vol@test.com", "status": "volunteer_assigned", "event_ids": {"personal": [], "clinic": []}}},
            "volunteers": {"vol@test.com": {"assigned_slots": ["slot1"]}}
        }
        mock_service.load_state.return_value = state
        with patch("cancel.resolve_slot", return_value=("slot1", state["slots"]["slot1"])):
            cancel_volunteer_booking("Volunteer", "vol@test.com", "slot1")
        self.assertIsNone(state["slots"]["slot1"]["volunteer"])
        self.assertEqual(state["slots"]["slot1"]["status"], "empty")
        self.assertEqual(state["volunteers"]["vol@test.com"]["assigned_slots"], [])

    @patch("cancel.CalendarService")
    def test_cancel_student_invalid_slot(self, mock_service_class):
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.load_state.return_value = {"slots": {}}
        with patch("cancel.resolve_slot", return_value=(None, None)):
            cancel_student_booking("Student", "student@test.com", "bad_slot")
        mock_service.save_state.assert_not_called()


# Clinic Tests

class TestClinicHelpers(unittest.TestCase):

    def test_normalize_slot_valid(self):
        result = clinic_normalize_slot("2026-06-10_14:00_JHB")
        self.assertEqual(result, "2026-06-10_14:00_JHB")

    def test_normalize_slot_invalid(self):
        with self.assertRaises(ValueError):
            clinic_normalize_slot("bad_format")


class TestRoleChecks(unittest.TestCase):

    def test_require_role_allowed(self):
        try:
            require_role("student", ["student", "admin"])
        except SystemExit:
            self.fail("require_role exited unexpectedly")

    def test_require_role_not_allowed(self):
        with self.assertRaises(SystemExit):
            require_role("student", ["admin"])


class TestPrintHelpers(unittest.TestCase):

    @patch("builtins.print")
    def test_divider_prints_line(self, mock_print):
        divider()
        mock_print.assert_called_with("-" * 55)

    @patch("builtins.print")
    def test_next_step_prints_instruction(self, mock_print):
        next_step("Check summary", "python3 clinic.py --summary")
        mock_print.assert_any_call("  NEXT STEP:")
        mock_print.assert_any_call("  Check summary")
        mock_print.assert_any_call("    python3 clinic.py --summary")


# Scheduler Tests

class TestSlotStatus(unittest.TestCase):

    def test_status_open_for_volunteer(self):
        slot = {"volunteer": None, "student": None}
        result = get_slot_display_status(slot, "volunteer")
        self.assertEqual(result, "OPEN — volunteer needed")

    def test_status_available_for_student(self):
        slot = {"volunteer": "vol@test.com", "student": None}
        result = get_slot_display_status(slot, "student")
        self.assertEqual(result, "AVAILABLE — ready to book")

    def test_status_booked_for_admin(self):
        slot = {"volunteer": "vol@test.com", "student": "stu@test.com"}
        result = get_slot_display_status(slot, "admin")
        self.assertEqual(result, "BOOKED | V: vol@test.com | S: stu@test.com")


class TestAvailabilityLogic(unittest.TestCase):

    def test_volunteer_slot_available(self):
        slot = {"volunteer": None, "student": None}
        self.assertTrue(is_slot_available_for_role(slot, "volunteer"))

    def test_student_slot_available(self):
        slot = {"volunteer": "vol@test.com", "student": None}
        self.assertTrue(is_slot_available_for_role(slot, "student"))

    def test_student_slot_not_available(self):
        slot = {"volunteer": None, "student": None}
        self.assertFalse(is_slot_available_for_role(slot, "student"))

    def test_admin_sees_all(self):
        slot = {"volunteer": None, "student": None}
        self.assertTrue(is_slot_available_for_role(slot, "admin"))


class TestSchedulerViews(unittest.TestCase):

    @patch("builtins.print")
    def test_display_summary_runs(self, mock_print):
        today = date.today().isoformat()
        state = {"slots": {f"{today}_14:00_JHB": {"volunteer": None, "student": None}}}
        display_summary(state, "volunteer", campus="JHB")
        self.assertTrue(mock_print.called)

    @patch("builtins.print")
    def test_view_day_returns_visible_slots_for_student(self, mock_print):
        today = date.today().isoformat()
        state = {"slots": {f"{today}_14:00_JHB": {"volunteer": "vol@test.com", "student": None, "status": "volunteer_assigned"}}}
        slots = view_day(state, 1, "student", campus="JHB")
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0][0], f"{today}_14:00_JHB")


if __name__ == "__main__":
    unittest.main()