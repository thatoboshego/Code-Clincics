from datetime import datetime, date, timedelta


def get_slot_display_status(slot, role):
    """
    Returns a human-readable status string for a slot based on the viewer's role.
    """
    volunteer = slot.get("volunteer")
    student = slot.get("student")

    if volunteer is None and student is None:
        if role == "volunteer":
            return "OPEN — volunteer needed"
        else:
            return "No volunteer yet"

    if volunteer is not None and student is None:
        if role == "student":
            return "AVAILABLE — ready to book"
        elif role == "volunteer":
            return "TAKEN — volunteer assigned"
        else:
            return f"Volunteer: {volunteer} | No student yet"

    if volunteer is not None and student is not None:
        if role == "admin":
            return f"BOOKED | V: {volunteer} | S: {student}"
        return "BOOKED — full"

    return "Unknown"


def is_slot_available_for_role(slot, role):
    """
    Determines whether a slot should be counted as 'available' for a given role.
    - Volunteer: slot has no volunteer yet
    - Student: slot has a volunteer but no student
    - Admin: any slot (all are visible)
    """
    volunteer = slot.get("volunteer")
    student = slot.get("student")

    if role == "volunteer":
        return volunteer is None
    elif role == "student":
        return volunteer is not None and student is None
    elif role == "admin":
        return True
    return False


def display_summary(state, role, campus=None):
    """
    Show a 7-day summary of available slots.
    For volunteers: counts slots with no volunteer assigned.
    For students: counts slots that have a volunteer but no student.
    For admins: counts all slots and shows booking status.
    """
    slots = state.get("slots", {})
    today = date.today()

    print("\nNext 7 Days Availability:")

    for i in range(7):
        current = today + timedelta(days=i)
        day_str = current.isoformat()
        day_label = current.strftime("%A %Y-%m-%d")

        # Filter slots for this day and campus
        day_slots = {
            k: v for k, v in slots.items()
            if k.startswith(day_str)
            and (campus is None or k.endswith(f"_{campus}"))
        }

        available_count = sum(
            1 for slot in day_slots.values()
            if is_slot_available_for_role(slot, role)
        )

        if role == "admin":
            booked = sum(1 for s in day_slots.values() if s.get("student") is not None)
            volunteered = sum(1 for s in day_slots.values() if s.get("volunteer") is not None)
            total = len(day_slots)
            print(f"{i+1}. {day_label} — {total} total | {volunteered} volunteered | {booked} booked")
        else:
            print(f"{i+1}. {day_label} ({available_count} available slots)")

    print()


def view_day(state, day_number, role, campus=None):
    """
    Display all slots for a specific day (1 = today).
    Returns a list of (slot_key, slot_data) tuples for the displayed slots,
    so the CLI can store them for --time selection.
    """
    slots = state.get("slots", {})
    today = date.today()

    if day_number < 1 or day_number > 7:
        print("Error: Day number must be between 1 and 7.")
        return []

    target_date = today + timedelta(days=day_number - 1)
    date_str = target_date.isoformat()
    day_label = target_date.strftime("%A, %d %B %Y")

    # Filter slots for this day and campus, sorted by time
    day_slots = sorted(
        [
            (k, v) for k, v in slots.items()
            if k.startswith(date_str)
            and (campus is None or k.endswith(f"_{campus}"))
        ],
        key=lambda x: x[0]
    )

    if not day_slots:
        print(f"\nNo slots found for {day_label}.")
        if campus:
            print(f"(Filtered by campus: {campus})")
        return []

    print(f"\nSlots for {day_label}:")
    print("-" * 55)

    # For volunteers and students, only show relevant/actionable slots
    # For admin, show everything
    visible_slots = []

    for slot_key, slot in day_slots:
        parts = slot_key.split("_")
        time_str = parts[1] if len(parts) >= 2 else "??"
        slot_campus = parts[2].replace("_", " ").title() if len(parts) == 3 else "Unknown"

        # Parse time range
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            dt_end = dt + timedelta(minutes=30)
            time_range = f"{dt.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
        except ValueError:
            time_range = time_str

        status = get_slot_display_status(slot, role)
        volunteer_email = slot.get("volunteer", "")
        student_email = slot.get("student", "")

        # Decide visibility per role
        if role == "volunteer":
            # Show open slots (no volunteer) so they can sign up
            if slot.get("volunteer") is None:
                visible_slots.append((slot_key, slot))
                idx = len(visible_slots)
                print(f"  [{idx:2}]  {time_range}  |  {slot_campus}  |  {status}")
            else:
                # Show taken slots greyed out (not selectable)
                print(f"  [  ]  {time_range}  |  {slot_campus}  |  {status}")

        elif role == "student":
            # Show slots that are ready to book (have volunteer, no student)
            if slot.get("volunteer") is not None and slot.get("student") is None:
                visible_slots.append((slot_key, slot))
                idx = len(visible_slots)
                print(f"  [{idx:2}]  {time_range}  |  {slot_campus}  |  {status}")
            else:
                print(f"  [  ]  {time_range}  |  {slot_campus}  |  {status}")

        elif role == "admin":
            # Show all slots
            visible_slots.append((slot_key, slot))
            idx = len(visible_slots)
            extra = ""
            if volunteer_email:
                extra += f" V: {volunteer_email}"
            if student_email:
                extra += f" | S: {student_email}"
            print(f"  [{idx:2}]  {time_range}  |  {slot_campus}  |  {slot.get('status','?')}{extra}")

    print("-" * 55)

    if not visible_slots:
        if role == "volunteer":
            print("  No open slots available for volunteering today.")
        elif role == "student":
            print("  No slots available for booking today.")
        print()
        return []

    if role == "volunteer":
        print(f"  {len(visible_slots)} slot(s) open for volunteering.")
    elif role == "student":
        print(f"  {len(visible_slots)} slot(s) available to book.")
    elif role == "admin":
        booked = sum(1 for _, s in day_slots if s.get("student") is not None)
        print(f"  {len(day_slots)} total slots | {booked} booked.")

    print()
    return visible_slots