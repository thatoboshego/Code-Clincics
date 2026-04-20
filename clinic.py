import argparse
import re
import os
from datetime import datetime, timedelta
from calendar_sync import CalendarService, load_state, save_state, verify_connection, CAMPUSES
from cancel import cancel_slot_cli
from booking import book_slot, volunteer_slot, is_volunteer_assigned
from scheduler import display_summary, view_day
from termcolor import colored




# Color Helpers

def success(msg):
    print(colored(msg, "green", attrs=["bold"]))

def error(msg):
    print(colored(msg, "red", attrs=["bold"]))

def info(msg):
    print(colored(msg, "cyan"))

def warn(msg):
    print(colored(msg, "yellow"))

def highlight(msg):
    print(colored(msg, "magenta", attrs=["bold"]))


# Helpers

def divider():
    print(colored("-" * 55, "blue"))


def next_step(instruction, command):
    print()
    divider()
    print(colored("  NEXT STEP:", "yellow", attrs=["bold"]))
    print(colored(f"  {instruction}", "white"))
    print()
    print(colored(f"    {command}", "cyan", attrs=["bold"]))
    divider()
    print()


def role_guidance_start(role):
    if role == "student":
        next_step(
            "Check the 7-day availability summary:",
            "python3 clinic.py --summary"
        )
    elif role == "volunteer":
        next_step(
            "View open slots you can volunteer for:",
            "python3 clinic.py --summary"
        )
    elif role == "admin":
        next_step(
            "View all confirmed bookings:",
            "python3 clinic.py --summary --password PASSWORD"
        )


def require_session(state):
    if "current_user" not in state:
        error("Error: No active session. Run --start first.")
        info("  python3 clinic.py --start --name 'Your Name' --email you@student.wethinkcode.co.za --role student --campus JHB")
        exit(1)


def require_role(current_role, allowed_roles):
    if current_role not in allowed_roles:
        error(f"Error: This action is only available to: {', '.join(allowed_roles)}.")
        exit(1)


def normalize_slot(slot_key):
    """Normalize slot key format for consistent lookups."""
    parts = slot_key.split("_")
    campus_suffix = f"_{parts[2]}" if len(parts) == 3 else ""
    base = f"{parts[0]}_{parts[1]}"
    try:
        dt = datetime.strptime(base, "%Y-%m-%d_%H:%M")
        return dt.strftime("%Y-%m-%d_%H:%M") + campus_suffix
    except ValueError:
        raise ValueError(f"Invalid slot key format: {slot_key}")


def slot_datetime(slot_key):
    """Extract datetime from a slot key."""
    parts = slot_key.split("_")
    return datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y-%m-%d_%H:%M")

#Set Admin Password
ADMIN_PASSWORD = os.getenv("CLINIC_ADMIN_PASSWORD", "Group14@")


# CLI Setup

parser = argparse.ArgumentParser(
    description=(
        "Code Clinic Booking CLI\n\n"
        "Commands:\n"
        "  --verify                 Check that Google Calendar connection works\n"
        "  --start                  Begin a new session (requires --name --email --role --campus)\n"
        "  --summary                View 7-day slot availability\n"
        "  --view N                 View slots for day N (1=today)\n"
        "  --time N                 Select slot N from the last --view\n"
        "  --book                   Book the selected slot (student only)\n"
        "  --volunteer              Sign up for the selected slot (volunteer only)\n"
        "  --myslots                View your current bookings or volunteered slots\n"
        "  --cancelslot N           Cancel slot number N from --myslots\n"
        "  --cancel SLOT_KEY        Cancel a booking or volunteer slot by key (advanced)\n"
        "  --campus CAMPUS          Filter by campus (JHB or CPT or EEC or CJC or SCC-G or SCC or SWGC )\n"
        "  --end                    End the session and logs user out."
    ),
    formatter_class=argparse.RawTextHelpFormatter
)

parser.add_argument("--verify", action="store_true",
                    help="Verify Google Calendar connection")
parser.add_argument("--start", action="store_true",
                    help="Start a new session")
parser.add_argument("--summary", action="store_true",
                    help="Show 7-day availability")
parser.add_argument("--view", type=int, metavar="DAY_NUMBER",
                    help="View slots for a specific day (1=today)")
parser.add_argument("--cancel", metavar="SLOT_KEY",
                    help="Cancel a booking or volunteer slot by slot key")
parser.add_argument("--myslots", action="store_true",
                    help="View your current bookings or volunteered slots")
parser.add_argument("--cancelslot", type=int, metavar="SLOT_NUMBER",
                    help="Cancel a slot by number from --myslots")
parser.add_argument("--time", type=int, metavar="SLOT_NUMBER",
                    help="Select a slot number from the last --view")
parser.add_argument("--book", action="store_true",
                    help="Book the currently selected slot")
parser.add_argument("--volunteer", action="store_true",
                    help="Volunteer for the currently selected slot")
parser.add_argument("--description", type=str,
                    help="Description of the help you need (used with --book)")
parser.add_argument("--role", choices=["student", "volunteer", "admin"],
                    help="Your role in the system")
parser.add_argument("--password", type=str,
                    help="Admin password (required when role is admin)")
parser.add_argument("--name", type=str,
                    help="Your full name")
parser.add_argument("--email", type=str,
                    help="Your WTC student email address")
parser.add_argument("--campus", choices=CAMPUSES,
                    help="Campus to filter or register for")
parser.add_argument("--end", action="store_true",
                    help="End the current session (logs you out)")

if __name__ == "__main__":
    args = parser.parse_args()

    # VERIFY

    if args.verify:
        state = load_state()
        user = state.get("current_user")
        if not user:
            error("Error: No active session. Run --start first to register your name.")
            exit(1)
        ok, message = verify_connection(user["name"])
        success(message) if ok else error(message)
        exit(0 if ok else 1)


    # START SESSION

    if args.start:
        if not args.name or not args.email or not args.role or not args.campus:
            error("Error: --start requires --name, --email, --role, and --campus")
            info("  Example: python3 clinic.py --start --name 'Jane Doe' --email jane@student.wethinkcode.co.za --role student --campus JHB")
            exit(1)

        if not re.fullmatch(r"[A-Za-z0-9._%+-]+@student\.wethinkcode\.co\.za", args.email):
            error("Error: Please use a valid WTC student email (must end in @student.wethinkcode.co.za)")
            exit(1)

        service = CalendarService(args.name, args.email)
        service.start_sync(args.campus)

        state = service.load_state()
        state["current_user"] = {
            "name": args.name,
            "email": args.email,
            "role": args.role,
            "campus": args.campus
        }
        service.save_state(state)

        print()
        highlight(f"  Hello {args.name}! Your session is now registered.")
        print(colored(f"  Role  : ", "white") + colored(args.role, "cyan", attrs=["bold"]))
        print(colored(f"  Campus: ", "white") + colored(args.campus, "cyan", attrs=["bold"]))
        role_guidance_start(args.role)
        info("Tip: End your session anytime with `python clinic.py --end`")
        exit(0)


    # Load session for all remaining commands

    state = load_state()
    require_session(state)

    current_user = state["current_user"]
    role = current_user["role"]  # FIX 1: Role always comes from session, never needs to be passed again
    campus = args.campus or current_user.get("campus")

    # --- END SESSION ---
    if args.end:
        name = current_user['name']
        state.pop("current_user", None)
        save_state(state)
        success(f"Session ended. Goodbye, {name}!")
        exit(0)

    # Admin password check (applied to all admin actions)

    if role == "admin":
        if not args.password:
            error("Error: Admin actions require --password PASSWORD after every command made by Admin.")
            exit(1)
        if args.password != ADMIN_PASSWORD:
            error("Error: Invalid admin password.")
            exit(1)


    # SUMMARY

    if args.summary:
        display_summary(state, role, campus=campus)
        if role == "admin":
            next_step(
            "Pick a day number to see its slots:",
            "python3 clinic.py --view 1 --password PASSWORD"
            )   
        else:
            next_step(
            "Pick a day number to see its slots:",
            "python3 clinic.py --view 1"
            )

        info("Tip: To end your session, run `python clinic.py --end`")

    # VIEW DAY

    elif args.view:
        day_number = args.view
        visible_slots = view_day(state, day_number, role, campus=campus)

        # FIX: filter out slots that have already passed
        now = datetime.now()
        visible_slots = [s for s in visible_slots if slot_datetime(s[0]) > now]

        if not visible_slots:
            warn("No upcoming slots available for this day.")
            exit(0)

        state["last_viewed_slots"] = [s[0] for s in visible_slots]
        save_state(state)

        # Show numbered list for admin too
        if role == "admin":
            print(colored(f"\nSlots for Day {day_number} (Admin):", "magenta", attrs=["bold"]))
            for idx, key in enumerate(state["last_viewed_slots"], start=1):
                slot = state["slots"][key]
                parts = key.split("_")
                date_str, time_str = parts[0], parts[1]
                campus_label = parts[2] if len(parts) > 2 else "Unknown"
                vol = slot.get("volunteer", "-")
                stu = slot.get("student", "-")
                print(f"[{idx}] {date_str} {time_str} | {campus_label} | V: {vol} S: {stu}")

            next_step(
                "Cancel a slot by its number:",
                "python3 clinic.py --cancelslot 1 --password PASSWORD"
            )
        else:
            # Existing student/volunteer logic
            if role == "student":
                next_step(
                    "Select a slot number to book:",
                    "python3 clinic.py --time 1"
                )
            elif role == "volunteer":
                next_step(
                    "Select a slot number to volunteer for:",
                    "python3 clinic.py --time 1"
                )

            info("Tip: To end your session, run `python clinic.py --end`")


    # SELECT TIME SLOT

    elif args.time:
        if "last_viewed_slots" not in state:
            error("Error: Run --view first to see available slots.")
            exit(1)

        slots = state["last_viewed_slots"]

        if args.time < 1 or args.time > len(slots):
            error(f"Error: Invalid selection. Choose a number between 1 and {len(slots)}.")
            exit(1)

        selected_key = normalize_slot(slots[args.time - 1])

        state["selected_slot"] = {
            "user_email": current_user["email"],
            "slot_key": selected_key,
            "role": role  # Role stored from session, not from user input
        }
        save_state(state)
        success(f"Slot {selected_key} selected.")

        if role == "student":
            next_step(
                "Book this slot:",
                "python3 clinic.py --book --description 'Describe the help you need'"
            )
        elif role == "volunteer":
            next_step(
                "Volunteer for this slot:",
                "python3 clinic.py --volunteer"
            )


    # BOOK SLOT

    elif args.book:
        require_role(role, ["student"])

        if "selected_slot" not in state:
            error("Error: No slot selected. Run --view then --time first.")
            exit(1)

        slot_key = normalize_slot(state["selected_slot"]["slot_key"])

        if slot_datetime(slot_key) < datetime.now():
            error(f"Cannot book slot {slot_key}: this time has already passed.")
            state.pop("selected_slot", None)
            save_state(state)
            exit(1)

        description = args.description or "Need help with coding"

        state = load_state()

        if not is_volunteer_assigned(slot_key, state):
            error(f"Cannot book slot {slot_key}: no volunteer is assigned to it.")
            exit(1)

        book_slot(current_user["name"], current_user["email"], slot_key, description)

        state = load_state()
        state.pop("selected_slot", None)
        save_state(state)

        next_step(
            "View or cancel your bookings:",
            "python3 clinic.py --myslots"
        )

        info("Tip: To end your session, run `python clinic.py --end`")

    # VOLUNTEER SLOT

    elif args.volunteer:
        require_role(role, ["volunteer"])

        if "selected_slot" not in state:
            error("Error: No slot selected. Run --view then --time first.")
            exit(1)

        slot_key = normalize_slot(state["selected_slot"]["slot_key"])

        if slot_datetime(slot_key) < datetime.now():
            error(f"Cannot volunteer for slot {slot_key}: this time has already passed.")
            state.pop("selected_slot", None)
            save_state(state)
            exit(1)

        volunteer_slot(current_user["name"], current_user["email"], slot_key)

        state = load_state()
        state.pop("selected_slot", None)
        save_state(state)

        next_step(
            "View or cancel your volunteered slots:",
            "python3 clinic.py --myslots"
        )

        info("Tip: To end your session, run `python clinic.py --end`")

    # MY SLOTS

    elif args.myslots:
        slots = state.get("slots", {})
        email = current_user["email"]

        if role == "student":
            my_slot_keys = state.get("students", {}).get(email, {}).get("booked_slots", [])
            label = "Your Booked Sessions"
            action_hint = "Cancel a booking:"
        elif role == "volunteer":
            my_slot_keys = state.get("volunteers", {}).get(email, {}).get("assigned_slots", [])
            label = "Your Volunteered Slots"
            action_hint = "Cancel a volunteered slot:"
        elif role == "admin":
            # Admin sees all active slots
            my_slot_keys = [k for k, v in slots.items() if v.get("student") or v.get("volunteer")]
            label = "All Active Slots"
            action_hint = "Cancel a slot (admin):"
        else:
            my_slot_keys = []
            label = "Your Slots"
            action_hint = "Cancel a slot:"

        # Filter to campus if set
        if campus:
            my_slot_keys = [k for k in my_slot_keys if k.endswith(f"_{campus}")]

        # Filter to only keys that still exist in slots
        my_slot_keys = [k for k in my_slot_keys if k in slots]

        print(colored(f"\n{label}:", "magenta", attrs=["bold"]))
        print(colored("-" * 60, "blue"))

        if not my_slot_keys:
            warn("  You have no active slots.")
            print()
        else:
            for idx, key in enumerate(sorted(my_slot_keys), start=1):
                slot = slots[key]
                parts = key.split("_")
                date_str, time_str = parts[0], parts[1]
                slot_campus = parts[2].replace("_", " ").title() if len(parts) == 3 else "Unknown"

                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    dt_end = dt + timedelta(minutes=30)
                    date_label = dt.strftime("%a %d %b %Y")
                    time_range = f"{dt.strftime('%H:%M')} - {dt_end.strftime('%H:%M')}"
                except ValueError:
                    date_label = date_str
                    time_range = time_str

                idx_str = colored(f"  [{idx}]", "yellow", attrs=["bold"])
                date_str_colored = colored(f"{date_label}  {time_range}", "white")
                campus_str = colored(f"{slot_campus}", "cyan")

                if role == "student":
                    vol = slot.get("volunteer", "No volunteer")
                    vol_colored = colored(f"Volunteer: {vol}", "green" if vol != "No volunteer" else "red")
                    print(f"{idx_str}  {date_str_colored}  |  {campus_str}  |  {vol_colored}")
                elif role == "volunteer":
                    stu = slot.get("student")
                    booked_label = colored(f"Booked by: {stu}", "green") if stu else colored("No student yet", "yellow")
                    print(f"{idx_str}  {date_str_colored}  |  {campus_str}  |  {booked_label}")
                elif role == "admin":
                    vol = slot.get("volunteer", "-")
                    stu = slot.get("student", "-")
                    print(f"{idx_str}  {date_str_colored}  |  {campus_str}  |  " +
                        colored(f"V: {vol}", "magenta") + "  " + colored(f"S: {stu}", "green"))

            print(colored("-" * 60, "blue"))
            print()

            state["my_slots_list"] = sorted(my_slot_keys)
            save_state(state)

            next_step(
                f"{action_hint}",
                "python3 clinic.py --cancelslot 1"
            )


    # CANCEL BY SLOT NUMBER (from --myslots)

    elif args.cancelslot:
    # For everyone, we rely on last_viewed_slots
        # Ensure we've viewed the slots first
        # CANCEL BY SLOT NUMBER (from --view)
        if "last_viewed_slots" not in state:
            error("Error: Run --view first to see available slots.")
            exit(1)

        slots_list = state["last_viewed_slots"]

        if not slots_list:
            warn("No active slots to cancel.")
            exit(0)

        # Validate selection
        if args.cancelslot < 1 or args.cancelslot > len(slots_list):
            error(f"Invalid selection. Choose a number between 1 and {len(slots_list)}.")
            exit(1)

        # Get slot key
        slot_key = normalize_slot(slots_list[args.cancelslot - 1])

        # Check slot exists
        slot = state["slots"].get(slot_key)
        if not slot:
            error(f"Error: Slot {slot_key} does not exist or has already been canceled.")
            exit(1)

        # ROLE-BASED CANCELLATION LOGIC

        # STUDENT: cancel ONLY themselves
        if role == "student":
            if slot.get("student") != current_user["email"]:
                error("Error: You can only cancel your own booking.")
                exit(1)

            slot["student"] = None
            success(f"Your booking for {slot_key} has been cancelled.")

        # VOLUNTEER: cancel ONLY if no student
        elif role == "volunteer":
            if slot.get("student"):
                error("Error: Cannot cancel — a student is booked in this slot.")
                exit(1)

            if slot.get("volunteer") != current_user["email"]:
                error("Error: You can only cancel your own volunteered slot.")
                exit(1)

            slot["volunteer"] = None
            success(f"You are no longer volunteering for {slot_key}.")

        # ADMIN: full control
        elif role == "admin":
            warn(f"Admin cancelling full slot: {slot_key}")
            cancel_slot_cli(current_user["name"], current_user["email"], slot_key, role)

            # Remove entire slot
            cancel_slot_cli(current_user["name"], current_user["email"], slot_key, role)

        
        # CLEANUP LOGIC
    

        # If slot still exists but now empty → delete it
        if slot_key in state["slots"]:
            slot = state["slots"][slot_key]
            if not slot.get("student") and not slot.get("volunteer"):
                cancel_slot_cli(current_user["name"], current_user["email"], slot_key, role)

        # Remove from last viewed list
        if slot_key in state.get("last_viewed_slots", []):
            state["last_viewed_slots"].remove(slot_key)

        save_state(state)

        next_step(
            "View updated availability:",
            "python3 clinic.py --view 1 --password PASSWORD" if role == "admin"
            else "python3 clinic.py --myslots"
        )

        info("Tip: To end your session, run `python clinic.py --end`")

    # CANCEL BY SLOT KEY (advanced / direct)

    elif args.cancel:
        slot_key = normalize_slot(args.cancel)
        warn(f"Cancelling slot: {slot_key}")
        cancel_slot_cli(current_user["name"], current_user["email"], slot_key, role)
        next_step(
            "View updated availability:",
            "python3 clinic.py --summary"
        )

        info("Tip: To end your session, run `python clinic.py --end`")


    # HELP (no command given)

    else:
        parser.print_help()