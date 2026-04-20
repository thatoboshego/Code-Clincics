from calendar_sync import CalendarService, PERSONAL_CALENDAR, CLINIC_CALENDAR
from booking import resolve_slot


def _delete_slot_events(service, slot):
    """
    Delete all calendar events stored in a slot, from the correct calendar.
    Handles both old flat list format and new {personal, clinic} dict format.
    """
    event_ids = slot.get("event_ids", {})

    if isinstance(event_ids, list):
        # Legacy format: best-effort delete from personal calendar
        for eid in event_ids:
            try:
                service.delete_event(eid, calendar_id=PERSONAL_CALENDAR)
            except Exception:
                pass
    elif isinstance(event_ids, dict):
        for eid in event_ids.get("personal", []):
            try:
                service.delete_event(eid, calendar_id=PERSONAL_CALENDAR)
            except Exception:
                pass
        for eid in event_ids.get("clinic", []):
            try:
                service.delete_event(eid, calendar_id=CLINIC_CALENDAR)
            except Exception:
                pass


# Cancel Student Booking

def cancel_student_booking(student_name, student_email, slot_key):
    service = CalendarService(student_name, student_email)
    state = service.load_state()

    resolved_key, slot = resolve_slot(slot_key, state.get("slots", {}))

    if slot is None:
        print("Invalid slot.")
        return
    if slot["student"] is None:
        print("No booking exists for this slot.")
        return
    if slot["student"] != student_email:
        print("You cannot cancel another student's booking.")
        return

    _delete_slot_events(service, slot)

    slot["student"] = None
    slot["status"] = "volunteer_assigned"
    slot["event_ids"] = {"personal": [], "clinic": []}

    if student_email in state.get("students", {}):
        booked = state["students"][student_email]["booked_slots"]
        state["students"][student_email]["booked_slots"] = [
            s for s in booked if s != resolved_key
        ]

    service.save_state(state)
    print("Student booking cancelled successfully.")


# Cancel Volunteer Slot

def cancel_volunteer_booking(volunteer_name, volunteer_email, slot_key):
    service = CalendarService(volunteer_name, volunteer_email)
    state = service.load_state()

    resolved_key, slot = resolve_slot(slot_key, state.get("slots", {}))

    if slot is None:
        print("Invalid slot.")
        return
    if slot["volunteer"] is None:
        print("No volunteer assigned to this slot.")
        return
    if slot["volunteer"] != volunteer_email:
        print("You cannot cancel another volunteer's slot.")
        return
    if slot["student"] is not None:
        print("Cannot cancel: a student has already booked this slot.")
        return

    _delete_slot_events(service, slot)

    slot["volunteer"] = None
    slot["status"] = "empty"
    slot["event_ids"] = {"personal": [], "clinic": []}

    if volunteer_email in state.get("volunteers", {}):
        assigned = state["volunteers"][volunteer_email]["assigned_slots"]
        state["volunteers"][volunteer_email]["assigned_slots"] = [
            s for s in assigned if s != resolved_key
        ]

    service.save_state(state)
    print("Volunteer availability cancelled.")


# CLI Cancel Controller

def cancel_slot_cli(name, email, slot_key, role):
    if role == "student":
        cancel_student_booking(name, email, slot_key)

    elif role == "volunteer":
        cancel_volunteer_booking(name, email, slot_key)

    elif role == "admin":
        service = CalendarService(name, email)
        state = service.load_state()

        resolved_key, slot = resolve_slot(slot_key, state.get("slots", {}))

        if slot is None:
            print("Invalid slot.")
            return

        original_student = slot["student"]
        original_volunteer = slot["volunteer"]

        _delete_slot_events(service, slot)

        slot["student"] = None
        slot["volunteer"] = None
        slot["status"] = "empty"
        slot["event_ids"] = {"personal": [], "clinic": []}

        # Clean up student and volunteer records
        if original_student and original_student in state.get("students", {}):
            state["students"][original_student]["booked_slots"] = [
                s for s in state["students"][original_student]["booked_slots"]
                if s != resolved_key
            ]
        if original_volunteer and original_volunteer in state.get("volunteers", {}):
            state["volunteers"][original_volunteer]["assigned_slots"] = [
                s for s in state["volunteers"][original_volunteer]["assigned_slots"]
                if s != resolved_key
            ]

        service.log_admin_action("cancel_slot", resolved_key, original_student, original_volunteer)
        service.save_state(state)
        print(f"Admin cancelled slot {resolved_key}")
