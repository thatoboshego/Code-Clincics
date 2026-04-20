import datetime
import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import standard libraries and Google Calendar API modules

SCOPES = ["https://www.googleapis.com/auth/calendar"]

PERSONAL_CALENDAR = "primary"
WTC_CALENDAR = "c_e9b0accb6c9385c400e119ed3eaabb64911ce4e76d7344cf410c5769c897f200@group.calendar.google.com"
CLINIC_CALENDAR = "c_824084569b1b0f1d8b60c8ccbcce5bf422aecd7f0dd0c6ef8bff47dcf26323d1@group.calendar.google.com"

HOME = os.path.expanduser("~")

CREDENTIALS_FILE = os.path.join("secrets", "credentials.json")
BASE_DIR = os.path.join(HOME, ".Student_data")
DATA_FILE = os.path.join(HOME, ".data", ".system_state.json")

CAMPUSES = ["JHB", "CPT", "EEC", "CJC", "SCC-G", "SCC","SWGC" ]


# State helpers (no auth required)

def load_state():
    """Load system state from disk without requiring Google auth."""
    if not os.path.exists(DATA_FILE):
        return {
            "slots": {},
            "students": {},
            "volunteers": {},
            "admin_logs": [],
            "last_synced": None
        }
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    """Save the current system state to a file."""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(state, f, indent=2)


# Google Auth -Creates a folder for a student & prepares a file path for storing their token

def get_student_path(student_name):
    student_dir = os.path.join(BASE_DIR, student_name)
    os.makedirs(student_dir, exist_ok=True)
    token_file = os.path.join(student_dir, "token.json")
    return token_file, student_dir


def authenticate_google(student_name):
    """Authenticate with Google and return a calendar service object."""
    if not student_name:
        raise ValueError("Cannot authenticate without a student name.")

    token_file, _ = get_student_path(student_name)
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    "Missing secrets/credentials.json — run --configure first."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def verify_connection(student_name):
    """
    Verify that the Google Calendar connection works for this student.
    Returns (True, message) or (False, message).
    """
    try:
        service = authenticate_google(student_name)
        service.calendarList().list(maxResults=1).execute()
        return True, "Google Calendar connection verified successfully."
    except FileNotFoundError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Connection failed: {e}"


# Calendar Service

class CalendarService:
    def __init__(self, student_name, student_email):
        self.student_name = student_name
        self.student_email = student_email
        # Only authenticate if a real name is given
        if student_name:
            self.service = authenticate_google(student_name)
        else:
            self.service = None

    def load_state(self):
        return load_state()

    def save_state(self, state):
        save_state(state)

    def log_admin_action(self, action_type, slot_key, original_student, original_volunteer):
        state = self.load_state()
        log_entry = {
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "admin_email": self.student_email,
            "action": action_type,
            "slot": slot_key,
            "original_student": original_student,
            "original_volunteer": original_volunteer
        }
        state["admin_logs"].append(log_entry)
        if len(state["admin_logs"]) > 500:
            state["admin_logs"] = state["admin_logs"][-500:]
        self.save_state(state)

    def clear_old_data(self, state):
        now = datetime.datetime.now()
        today = now.date()

        def slot_is_future(key):
            try:
                parts = key.split("_")
                slot_dt = datetime.datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M")
                return slot_dt > now
            except (ValueError, IndexError):
                return datetime.date.fromisoformat(key.split("_")[0]) > today

        new_slots = {k: v for k, v in state["slots"].items() if slot_is_future(k)}
        state["slots"] = new_slots

        for email in list(state["students"].keys()):
            state["students"][email]["booked_slots"] = [
                s for s in state["students"][email]["booked_slots"] if s in new_slots
            ]
            if not state["students"][email]["booked_slots"]:
                del state["students"][email]

        for email in list(state["volunteers"].keys()):
            state["volunteers"][email]["assigned_slots"] = [
                s for s in state["volunteers"][email]["assigned_slots"] if s in new_slots
            ]
            if not state["volunteers"][email]["assigned_slots"]:
                del state["volunteers"][email]

        return state

    def start_sync(self, campus):
        """
        Sync the next 7 days of slots for a given campus.
        Skips re-creating slots that already exist (preserves bookings).
        Tracks synced campuses per day so switching campus always syncs the new one.
        """
        state = self.load_state()
        state = self.clear_old_data(state)

        today = datetime.datetime.now(datetime.timezone.utc).date()
        now = datetime.datetime.now()
        today_str = today.isoformat()

        # Track which campuses have been synced today
        synced_campuses = state.get("synced_campuses", {})

        # Reset tracking if it is a new day
        if (state.get("last_synced") or "")[:10] != today_str:
            synced_campuses = {}

        # Skip only if this specific campus was already synced today
        if today_str in synced_campuses and campus in synced_campuses.get(today_str, []):
            print(f"Calendar data is already up to date for campus: {campus}")
            return

        for i in range(7):
            current = today + datetime.timedelta(days=i)
            for hour in range(8, 17):
                for minute in (0, 30):
                    # Skip slots that have already passed
                    slot_dt = datetime.datetime.combine(current, datetime.time(hour, minute))
                    if slot_dt <= now:
                        continue

                    key = f"{current}_{hour:02}:{minute:02}_{campus}"
                    if key not in state["slots"]:
                        state["slots"][key] = {
                            "student": None,
                            "volunteer": None,
                            "status": "empty",
                            "event_ids": {"personal": [], "clinic": []},
                            "campus": campus
                        }

        # Mark this campus as synced today
        synced_campuses.setdefault(today_str, [])
        if campus not in synced_campuses[today_str]:
            synced_campuses[today_str].append(campus)

        state["last_synced"] = today_str
        state["synced_campuses"] = synced_campuses
        self.save_state(state)
        print(f"System synced successfully for campus: {campus}")

    def add_event_to_calendar(self, slot_key, title, description, duration_minutes=30, calendar_id=PERSONAL_CALENDAR, attendees=None):
        """Add an event to Google Calendar and return its event ID."""
        if not self.service:
            raise RuntimeError("No authenticated Google service available.")
     
        parts = slot_key.split("_")
        date_str = parts[0]
        time_str = parts[1]
        start_dt = datetime.datetime.fromisoformat(date_str + "T" + time_str)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
            "attendees": [{"email": email} for email in attendees] if attendees else []
        }

        created_event = self.service.events().insert(calendarId=calendar_id, body=event, sendUpdates="all" if attendees else "none").execute()
        return created_event["id"]

    def delete_event(self, event_id, calendar_id=PERSONAL_CALENDAR):
        """Delete a Google Calendar event by ID."""
        if not self.service:
            raise RuntimeError("No authenticated Google service available.")
        try:
            self.service.events().delete(calendarId=calendar_id, eventId=event_id, sendUpdates="all").execute()
        except HttpError as e:
            if e.resp.status == 410:
                pass 
            else:
                raise

    def update_event(self, event_id, slot_key, title, description, duration_minutes=30, calendar_id=PERSONAL_CALENDAR, attendees=None):
        """Update an existing event and optionally send invites."""
        if not self.service:
            raise RuntimeError("No authenticated Google service available.")

        parts = slot_key.split("_")
        date_str = parts[0]
        time_str = parts[1]

        start_dt = datetime.datetime.fromisoformat(date_str + "T" + time_str)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

        event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Africa/Johannesburg"},
        "attendees": [{"email": email} for email in attendees] if attendees else []
        }

        updated_event = self.service.events().update(
        calendarId=calendar_id,
        eventId=event_id,
        body=event,
        sendUpdates="all" if attendees else "none"
        ).execute()

        return updated_event["id"]
    
    