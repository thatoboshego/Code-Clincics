from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from calendar_sync import CalendarService, load_state, PERSONAL_CALENDAR


# Slot Key Normalization

def normalize_slot(slot_key):
    """
    Convert a slot string into standardized format: YYYY-MM-DD_HH:MM_campus
    The campus suffix is preserved if present.
    """
    if isinstance(slot_key, datetime):
        return slot_key.strftime("%Y-%m-%d_%H:%M")

    if not isinstance(slot_key, str):
        raise ValueError(f"Cannot normalize slot key: {slot_key}")

    # Split off campus suffix if present
    parts = slot_key.split("_")
    campus_suffix = ""
    if len(parts) == 3:
        campus_suffix = f"_{parts[2]}"
        slot_key = f"{parts[0]}_{parts[1]}"

    for fmt in ("%Y-%m-%d_%H:%M", "%Y-%m-%d_%H"):
        try:
            dt = datetime.strptime(slot_key, fmt)
            return dt.strftime("%Y-%m-%d_%H:%M") + campus_suffix
        except ValueError:
            continue

    raise ValueError(f"Cannot normalize slot key: {slot_key}")


def resolve_slot(slot_key, slots):
    """
    Find a slot in the slots dict by normalized key.
    Returns (resolved_key, slot_data) or (None, None) if not found.
    """
    normalized = normalize_slot(slot_key)
    if normalized in slots:
        return normalized, slots[normalized]
    for k, v in slots.items():
        try:
            if normalize_slot(k) == normalized:
                return k, v
        except ValueError:
            continue
    return None, None


# Email Notification

def send_booking_emails(student_name, student_email, volunteer_email, slot_key, description, state):
    """
    Send confirmation emails to both student and volunteer after a booking is confirmed.
    Reads SMTP config from environment variables: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD.
    Falls back to printing if email is not configured.
    """
    parts = slot_key.split("_")
    date_str, time_str = parts[0], parts[1]
    campus = parts[2].replace("_", " ").title() if len(parts) == 3 else "Unknown"

    dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    dt_end = dt_start + timedelta(minutes=30)
    readable_date = dt_start.strftime("%A, %d %B %Y")
    readable_time = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"

    volunteer_name = "Volunteer"
    if volunteer_email and volunteer_email in state.get("volunteers", {}):
        volunteer_name = state["volunteers"][volunteer_email].get("name", "Volunteer")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    emails_to_send = [
        {
            "to": student_email,
            "subject": "Code Clinic Booking Confirmed",
            "body": (
                f"Hi {student_name},\n\n"
                f"Your Code Clinic session has been confirmed!\n\n"
                f"  Date     : {readable_date}\n"
                f"  Time     : {readable_time}\n"
                f"  Campus   : {campus}\n"
                f"  Volunteer: {volunteer_name} ({volunteer_email})\n\n"
                f"What you need help with:\n{description}\n\n"
                f"Please make sure you are on time. Good luck!\n\n"
                f"— WeThinkCode_ Code Clinic"
            )
        },
        {
            "to": volunteer_email,
            "subject": "Code Clinic Session Booked",
            "body": (
                f"Hi {volunteer_name},\n\n"
                f"A student has booked your Code Clinic slot.\n\n"
                f"  Date   : {readable_date}\n"
                f"  Time   : {readable_time}\n"
                f"  Campus : {campus}\n"
                f"  Student: {student_name} ({student_email})\n\n"
                f"What they need help with:\n{description}\n\n"
                f"Thank you for volunteering your time!\n\n"
                f"— WeThinkCode_ Code Clinic"
            )
        }
    ]

    if not smtp_host or not smtp_user or not smtp_password:
        print("\nEMAIL NOTIFICATIONS (SMTP not configured — printing instead)")
        for mail in emails_to_send:
            print(f"\nTo: {mail['to']}")
            print(f"Subject: {mail['subject']}")
            print(mail['body'])
        print()
        return

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            for mail in emails_to_send:
                msg = MIMEMultipart()
                msg["From"] = smtp_user
                msg["To"] = mail["to"]
                msg["Subject"] = mail["subject"]
                msg.attach(MIMEText(mail["body"], "plain"))
                server.sendmail(smtp_user, mail["to"], msg.as_string())
        print("Confirmation emails sent to student and volunteer.")
    except Exception as e:
        print(f"Warning: Could not send emails — {e}")
        print("Booking was still saved successfully.")


# Volunteer Check

def is_volunteer_assigned(slot_key, state=None):
    """Check whether a volunteer is assigned to the given slot."""
    if state is None:
        state = load_state()
    _, slot = resolve_slot(slot_key, state.get("slots", {}))
    return slot is not None and slot.get("volunteer") is not None


# Student Check

def is_student_booked(slot_key, state=None):
    """Check whether a student has already booked the given slot."""
    if state is None:
        state = load_state()
    _, slot = resolve_slot(slot_key, state.get("slots", {}))
    return slot is not None and slot.get("student") is not None


# Student Booking-here we are booking a time slot for the student in the calender system

def book_slot(student_name, student_email, slot_key, description):
    service = CalendarService(student_name, student_email)
    state = service.load_state()

    resolved_key, slot = resolve_slot(slot_key, state.get("slots", {}))

    if slot is None:
        print(f"Invalid slot: {slot_key}. Please run --summary and --view to pick a valid slot.")
        return
    if slot.get("volunteer") is None:
        print("Cannot book slot because no volunteer is assigned.")
        return
    if slot.get("student") is not None:
        print("Slot already booked.")
        return

    volunteer_email = slot.get("volunteer")
    volunteer_name = state["volunteers"][volunteer_email]["name"]


    title = f"Code Clinic - {student_name}"
    desc = f"Student: {student_name}\nEmail: {student_email}\n\nHelp needed:\n{description}"

    attendees = [student_email, volunteer_email]

    if not slot["event_ids"]["personal"]:
        print("No existing event to update")
        return

    # Get existing volunteer event (personal calendar)
    existing_event_id = slot["event_ids"]["personal"][0]

    # Use volunteer account to update event
    volunteer_service = CalendarService(volunteer_name, volunteer_email) 


    updated_event_id = volunteer_service.update_event(
    existing_event_id,
    resolved_key,
    title,
    desc,
    calendar_id=PERSONAL_CALENDAR,
    attendees=attendees
)
    slot["student"] = student_email
    slot["status"] = "confirmed"
    # Store event IDs per calendar so cancellation deletes from the right place
    slot.setdefault("event_ids", {"personal": [], "clinic": []})
    slot["event_ids"]["personal"] = [updated_event_id]

    state.setdefault("students", {}).setdefault(student_email, {"name": student_name, "booked_slots": []})
    state["students"][student_email]["booked_slots"].append(resolved_key)

    service.save_state(state)
    print(f"Booking confirmed for {resolved_key}")
    print("Google Calendar updated.")

    send_booking_emails(student_name, student_email, volunteer_email, resolved_key, description, state)


# Volunteer Signup -Assign a volunteer to a specific time slot and create a calendar event for them.

def volunteer_slot(volunteer_name, volunteer_email, slot_key):
    service = CalendarService(volunteer_name, volunteer_email)
    state = service.load_state()

    resolved_key, slot = resolve_slot(slot_key, state.get("slots", {}))

    if slot is None:
        print(f"Invalid slot: {slot_key}. Please run --summary and --view to pick a valid slot.")
        return
    if slot.get("volunteer") is not None:
        print("This slot already has a volunteer.")
        return

    title = "Volunteer - Code Clinic"
    desc = f"Volunteer: {volunteer_name}\nEmail: {volunteer_email}"

    personal_event_id = service.add_event_to_calendar(resolved_key, title, desc, calendar_id=PERSONAL_CALENDAR)


    slot["volunteer"] = volunteer_email
    slot["status"] = "volunteer_assigned"
    slot.setdefault("event_ids", {"personal": [], "clinic": []})
    slot["event_ids"]["personal"].append(personal_event_id)

    state.setdefault("volunteers", {}).setdefault(volunteer_email, {"name": volunteer_name, "assigned_slots": []})
    state["volunteers"][volunteer_email]["assigned_slots"].append(resolved_key)

    service.save_state(state)
    print(f"Volunteer slot confirmed for {resolved_key}")
    print("Calendar updated.")
