# WeThinkCode\_ Code Clinic

> A command-line scheduling and booking system for the WeThinkCode\_ Code Clinic programme — connecting students with volunteer mentors across multiple campuses, with real-time Google Calendar integration and email notifications.



## Table of Contents

- [About the Project](#about-the-project)
- [Features](#features)
- [System Requirements Compliance](#system-requirements-compliance)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [How to Run the Project](#how-to-run-the-project)
- [Command Reference](#command-reference)
- [Full Usage Walkthrough](#full-usage-walkthrough)
- [Output & Piping](#output--piping)
- [Data Storage](#data-storage)
- [Running Tests](#running-tests)



## About the Project

The **WeThinkCode\_ Code Clinic** is a peer-support coding programme where students can book 30-minute sessions with volunteer mentors for coding help and guidance. This CLI application manages the entire lifecycle of those sessions:

- Students browse available time slots and book sessions with assigned volunteers
- Volunteers register their availability for specific time slots
- Admins oversee and manage all bookings across campuses
- All sessions are synchronised with **both** the student's personal Google Calendar and the Coding Clinic's shared Google Calendar in real time
- Booking confirmations are sent via **email** to both parties

All session state is stored locally at `~/.data/.system_state.json` in JSON format. Configuration and OAuth tokens are stored in a hidden directory in the user's home folder (`~/.Student_data/`).



## Features

| Feature                  | Description                                                             |
| ------------------------ | ----------------------------------------------------------------------- |
| **Student Booking**      | Browse open slots and book a 30-minute session with a volunteer         |
| **Volunteer Sign-up**    | Register availability for specific time slots across the day            |
| **Admin Management**     | View, cancel, and audit any booking or volunteer assignment             |
| **Google Calendar Sync** | Events are created, updated, and deleted in real time                   |
| **Email Notifications**  | Confirmation emails sent to both student and volunteer on booking       |
| **Multi-Campus Support** | Manage sessions across all WeThinkCode\_ campus locations               |
| **Role-Based Access**    | Students, volunteers, and admins each see only what is relevant to them |
| **Session Persistence**  | State is saved locally — no need to re-authenticate on every command    |
| **Past Slot Filtering**  | Expired slots are automatically hidden and cleaned up                   |



## System Requirements Compliance

This section maps every requirement from the project specification to the corresponding behaviour in the system.

### Core System Behaviour

| Requirement                                   | Status | How It Is Met                                                                  |
| --------------------------------------------- | ------ | ------------------------------------------------------------------------------ |
| Runs on Linux                                 | Done   | Pure Python 3 — compatible with all Linux distributions used on campus         |
| Takes command-line arguments                  | Done   | All interaction is via `argparse` flags (e.g. `--start`, `--book`, `--cancel`) |
| Has a `--help` command                        | Done   | `python3 clinic.py --help` prints all available flags and descriptions         |
| Output to standard output                     | Done   | All output is printed to stdout and can be piped or redirected                 |
| Output can be piped to a file                 | Done   | `python3 clinic.py --summary > output.txt` works with standard Linux piping    |
| Internal data stored as JSON                  | Done   | State stored in `~/.data/.system_state.json`                                   |
| Configuration stored in hidden home directory | Done   | OAuth tokens stored at `~/.Student_data/<n>/token.json`                        |

### Configure the System

| Requirement                                | Status | How It Is Met                                                          |
| ------------------------------------------ | ------ | ---------------------------------------------------------------------- |
| Connect to WeThinkCode\_ Google Calendar   | Done   | OAuth 2.0 authentication via `secrets/credentials.json` on `--start`   |
| Connect to the Code Clinic Google Calendar | Done   | `CLINIC_CALENDAR` ID configured in `calendar_sync.py`                  |
| Verify connection is working               | Done   | `python3 clinic.py --verify` checks the Google Calendar API connection |

### View Calendars

| Requirement                                    | Status | How It Is Met                                                                         |
| ---------------------------------------------- | ------ | ---------------------------------------------------------------------------- |
| Download next 7 days of data                   | Done   | `start_sync()` generates slots for the next 7 days from today                         |
| Weekends and public holidays counted in 7 days | Done   | All 7 days are included; no days are skipped                                          |
| Data stored in a local file                    | Done   | Stored in `~/.data/.system_state.json`                                                |
| Data updated each time tool is run             | Done   | `start_sync()` refreshes slots on every `--start`                                     |
| Skip download if data is already up to date    | Done   | `synced_campuses` tracking prevents re-syncing the same campus on the same day        |
| Old data discarded                             | Done   | `clear_old_data()` removes any slots whose datetime has passed                        |
| Display in a readable layout                   | Done   | `--summary` shows a 7-day count view; `--view N` shows a formatted slot table per day |

### Make a Booking

| Requirement                                        | Status | How It Is Met                                                                    |
| -------------------------------------------------- | ------ | ------------------------------------------------------------------------- |
| Book by specifying date and time                   | Done   | User selects a slot via `--view N` then `--time N` then `--book`                 |
| All calendars updated on booking                   | Done   | Volunteer's personal calendar event is updated with student as an attendee       |
| Data file updated with booking info                | Done   | `state['slots']` and `state['students']` updated and saved to JSON               |
| Slot can only be booked if a volunteer is assigned | Done   | `book_slot()` checks `slot['volunteer'] is not None` before proceeding           |
| Booking requires a description of help needed      | Done   | `--description "..."` used with `--book`; defaults to a fallback if omitted      |
| Duration is 30 minutes                             | Done   | All events created with a 30-minute end time (`duration_minutes=30`)             |
| No double booking of already-booked slots          | Done   | `book_slot()` checks `slot['student'] is not None` and blocks duplicate bookings |

### Volunteer for a Slot

| Requirement                                             | Status | How It Is Met                                                               |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| Indicate availability for a specific slot               | Done   | `--volunteer` signs the user up for the selected slot                       |
| No double booking for volunteers                        | Done   | `volunteer_slot()` checks `slot['volunteer'] is not None` before assigning  |
| Booking appears on volunteer's personal Google Calendar | Done   | `add_event_to_calendar()` creates an event on `PERSONAL_CALENDAR` (primary) |
| Data file updated                                       | Done   | `state['slots']` and `state['volunteers']` saved to JSON after sign-up      |

### Cancel Booking (Student)

| Requirement                              | Status | How It Is Met                                                          |
| ---------------------------------------- | ------ | ---------------------------------------------------------------------- |
| Student can cancel their own booking     | Done   | `cancel_student_booking()` removes the student from the slot           |
| Cannot cancel an empty slot              | Done   | Function checks `slot['student'] is None` and blocks the action        |
| Cannot cancel another student's booking  | Done   | Email match check: `slot['student'] != student_email` exits with error |
| Cancelling does not remove the volunteer | Done   | Only `slot['student']` is cleared; `slot['volunteer']` is preserved    |
| Data file updated                        | Done   | State saved to JSON and Google Calendar event deleted or updated       |

### Cancel Volunteering

| Requirement                                   | Status | How It Is Met                                                              |
| --------------------------------------------- | ------ | -------------------------------------------------------------------------- |
| Volunteer can cancel their availability       | Done   | `cancel_volunteer_booking()` removes the volunteer from the slot           |
| Cannot cancel if a student has already booked | Done   | Function checks `slot['student'] is not None` and blocks the action        |
| Cannot cancel another volunteer's slot        | Done   | Email match check: `slot['volunteer'] != volunteer_email` exits with error |
| Data file updated                             | Done   | State saved to JSON and Google Calendar event deleted                      |

### Bonus Requirements

| Bonus Requirement                       | Status | Notes                                                             |
| --------------------------------------- | ------ | ----------------------------------------------------------------- |
| Multiple configuration files (per user) | Done   | Each user has their own token at `~/.Student_data/<n>/token.json` |



## Project Structure


fun-ex-code-clinics/
│
├── clinic.py           # Main entry point — CLI argument parsing and session management
├── calendar_sync.py    # Google Calendar authentication, API calls, and state persistence
├── booking.py          # Student and volunteer booking logic, email notifications
├── cancel.py           # Cancellation logic for students, volunteers, and admins
├── scheduler.py        # 7-day summary and slot display logic
├── test_main.py        # Full unit test suite (unittest + mocking)
├── requirements.txt    # pip dependencies
├── README.md           # This file
│
└── secrets/
    └── credentials.json    # Google OAuth 2.0 credentials (not committed — see Setup)




## Prerequisites

- **Python 3.8+**
- A **Google account** with access to Google Calendar
- A **Google Cloud project** with the Calendar API enabled and OAuth 2.0 credentials downloaded

**Python dependencies:**


google-api-python-client
google-auth-httplib2
google-auth-oauthlib
termcolor



## Setup & Installation

### 1. Clone the Repository

```bash
git clone <repo-url>
cd fun-ex-code-clinics
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Google Calendar Credentials

This project requires OAuth 2.0 credentials from the Google Cloud Console.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library** and enable the **Google Calendar API**
4. Navigate to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth 2.0 Client ID**
6. Choose **Desktop app** as the application type
7. Download the credentials JSON file
8. Place it at `secrets/credentials.json` in the project root

```
fun-ex-code-clinics/
└── secrets/
    └── credentials.json   # Place your downloaded file here
```

> **Never commit `credentials.json` or token files to version control.**


## Configuration

### Email Notifications (Optional)

Email notifications are sent via SMTP when a booking is confirmed. Configure the following environment variables:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT=587
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
```

> If SMTP is not configured, email content will be printed to the console as a fallback. Bookings are still saved successfully.

### Admin Password (Optional)

```bash
export CLINIC_ADMIN_PASSWORD="your-secure-password"
```

> If not set, a default password is used. It is strongly recommended to set this in a production environment.



## How to Run the Project

### Getting Help

Run this at any time to see all available flags and descriptions:

```bash
python3 clinic.py --help
```


usage: clinic.py [-h] [--verify] [--start] [--summary] [--view DAY_NUMBER]
                 [--cancel SLOT_KEY] [--myslots] [--cancelslot SLOT_NUMBER]
                 [--time SLOT_NUMBER] [--book] [--volunteer]
                 [--description DESCRIPTION] [--role {student,volunteer,admin}]
                 [--password PASSWORD] [--name NAME] [--email EMAIL]
                 [--campus {JHB,CPT,EEC,CJC,SCC-G,SCC,SWGC}]

Code Clinic Booking CLI

Commands:
  --verify                 Check that Google Calendar connection works
  --start                  Begin a new session (requires --name --email --role --campus)
  --summary                View 7-day slot availability
  --view N                 View slots for day N (1=today)
  --time N                 Select slot N from the last --view
  --book                   Book the selected slot (student only)
  --volunteer              Sign up for the selected slot (volunteer only)
  --myslots                View your current bookings or volunteered slots
  --cancelslot N           Cancel slot number N from --myslots
  --cancel SLOT_KEY        Cancel a booking or volunteer slot by key (advanced)
  --campus CAMPUS          Filter by campus
```

### Step 1 — Start a Session

Every user (student, volunteer, or admin) must start a session before using any other command. This authenticates with Google and generates the 7-day slot grid for your campus.

```bash
python3 clinic.py --start --name "Andiswa Ndzimande" --email anndzeec025@student.wethinkcode.co.za --role student --campus JHB
```

> Your email **must** end in `@student.wethinkcode.co.za`. A browser window will open for Google authentication on first use.

### Step 2 — Verify Your Google Calendar Connection

```bash
python3 clinic.py --verify
```

### Step 3 — Use the System

Once your session is active, all subsequent commands use your stored session. You do not need to re-enter your name, email, or role again.

```bash
python3 clinic.py --summary          # See what's available this week
python3 clinic.py --view 1           # See today's slots in detail
python3 clinic.py --time 2           # Select slot number 2 from the list
python3 clinic.py --book --description "Need help with recursion"
```

---

## Command Reference

| Command             | Arguments                              | Role      | Description                                           |
| ------------------- | -------------------------------------- | --------- | ----------------------------------------------------- |
| `--start`           | `--name` `--email` `--role` `--campus` | All       | Register a session and authenticate with Google       |
| `--verify`          | —                                      | All       | Check that Google Calendar connection works           |
| `--summary`         | `[--campus CAMPUS]`                    | All       | Show a 7-day availability overview                    |
| `--view N`          | `[--campus CAMPUS]`                    | All       | View all slots for day N (1 = today, up to 7)         |
| `--time N`          | —                                      | All       | Select slot number N from the last `--view` output    |
| `--book`            | `[--description "text"]`               | Student   | Book the currently selected slot                      |
| `--volunteer`       | —                                      | Volunteer | Sign up for the currently selected slot               |
| `--myslots`         | `[--campus CAMPUS]`                    | All       | View your current bookings or volunteered slots       |
| `--cancelslot N`    | —                                      | All       | Cancel slot number N from the last `--myslots` output |
| `--cancel SLOT_KEY` | —                                      | All       | Cancel a slot directly by its key (advanced)          |

### Role Options

| Role        | Access                                                                               |
| ----------- | ------------------------------------------------------------------------------------ |
| `student`   | View available slots, book sessions, cancel own bookings                             |
| `volunteer` | View open slots, sign up for sessions, cancel own volunteer slots (only if unbooked) |
| `admin`     | View all slots, cancel any booking or volunteer assignment, full audit log           |

### Campus Codes

| Code    | Campus               |
| ------- | -------------------- |
| `JHB`   | Johannesburg         |
| `CPT`   | Cape Town            |
| `EEC`   | East Entrance Campus |
| `CJC`   | CJ Campus            |
| `SCC-G` | SCC Gauteng          |
| `SCC`   | SCC                  |
| `SWGC`  | SWGC Campus          |

---

## Full Usage Walkthrough

### Student Workflow

**1. Start a session**

```bash
python3 clinic.py --start \
  --name "Remington Masilela" \
  --email remi@student.wethinkcode.co.za \
  --role student \
  --campus JHB
```

**2. Check what's available this week**

```bash
python3 clinic.py --summary
```

```
Next 7 Days Availability:
1. Monday 2026-06-10    (3 available slots)
2. Tuesday 2026-06-11   (5 available slots)
3. Wednesday 2026-06-12 (2 available slots)
...
```

**3. View a specific day's slots**

```bash
python3 clinic.py --view 1
```

```
Slots for Monday, 10 June 2026:
-------------------------------------------------------
  [ 1]  08:00 - 08:30  |  Jhb  |  AVAILABLE — ready to book
  [  ]  08:30 - 09:00  |  Jhb  |  BOOKED — full
  [ 2]  09:00 - 09:30  |  Jhb  |  AVAILABLE — ready to book
-------------------------------------------------------
  2 slot(s) available to book.
```

**4. Select a slot**

```bash
python3 clinic.py --time 1
```

```
Slot 2026-06-10_08:00_JHB selected.
```

**5. Book the slot**

```bash
python3 clinic.py --book --description "I need help understanding Python decorators and how to use them in my project."
```

```
Booking confirmed for 2026-06-10_08:00_JHB
   Google Calendar updated.
   Confirmation emails sent to student and volunteer.
```

**6. View your bookings**

```bash
python3 clinic.py --myslots
```

**7. Cancel a booking**

```bash
python3 clinic.py --myslots           # find the slot number
python3 clinic.py --cancelslot 1      # cancel it
```

### Volunteer Workflow

**1. Start a session**

```bash
python3 clinic.py --start \
  --name "Anele Dludla" \
  --email anele@student.wethinkcode.co.za \
  --role volunteer \
  --campus JHB
```

**2. View open slots**

```bash
python3 clinic.py --view 2
```

```
Slots for Tuesday, 11 June 2026:
-------------------------------------------------------
  [ 1]  10:00 - 10:30  |  Jhb  |  OPEN — volunteer needed
  [ 2]  10:30 - 11:00  |  Jhb  |  OPEN — volunteer needed
  [  ]  11:00 - 11:30  |  Jhb  |  TAKEN — volunteer assigned
-------------------------------------------------------
  2 slot(s) open for volunteering.
```

**3. Select a slot and sign up**

```bash
python3 clinic.py --time 1
python3 clinic.py --volunteer
```

```
Volunteer slot confirmed for 2026-06-11_10:00_JHB
   Calendar updated.
```

**4. Cancel a volunteered slot** _(only possible if no student has booked yet)_

```bash
python3 clinic.py --myslots
python3 clinic.py --cancelslot 1
```

---

### Admin Workflow

**1. Start a session**

```bash
python3 clinic.py --start \
  --name "Thato Bushigo" \
  --email thato@student.wethinkcode.co.za \
  --role admin \
  --campus JHB
```

**2. View full summary**

```bash
python3 clinic.py --summary --password your-admin-password
```

```
Next 7 Days Availability:
1. Monday 2026-06-10    — 18 total | 5 volunteered | 3 booked
2. Tuesday 2026-06-11   — 18 total | 7 volunteered | 6 booked
...
```

**3. View, manage, and cancel slots**

```bash
python3 clinic.py --view 1 --password your-admin-password       # view all slots for a day
python3 clinic.py --myslots --password your-admin-password      # view all active slots
python3 clinic.py --cancelslot 3 --password your-admin-password # cancel by number
python3 clinic.py --cancel 2026-06-10_08:00_JHB --password your-admin-password  # cancel by key
```

```
Cancelling slot: 2026-06-10_08:00_JHB
Admin cancelled slot 2026-06-10_08:00_JHB
```



## Output & Piping

All command output is written to **standard output (stdout)**, fully compatible with standard Linux piping and redirection.

**Redirect output to a file:**

```bash
python3 clinic.py --summary > availability.txt
python3 clinic.py --view 1 > today_slots.txt
python3 clinic.py --myslots > my_bookings.txt
```

**Pipe output to another tool:**

```bash
python3 clinic.py --summary | grep "available"
python3 clinic.py --view 1 | less
```


## Data Storage

All booking and session data is stored locally in a **JSON file** at `~/.data/.system_state.json`, created automatically on first use.

```json
{
  "slots": {
    "2026-06-10_14:00_JHB": {
      "student": null,
      "volunteer": "oratile@student.wethinkcode.co.za",
      "status": "volunteer_assigned",
      "event_ids": { "personal": ["<google_event_id>"], "clinic": [] },
      "campus": "EEC"
    }
  },
  "students": { "email": { "name": "", "booked_slots": [] } },
  "volunteers": { "email": { "name": "", "assigned_slots": [] } },
  "last_synced": "2026-06-10",
  "synced_campuses": { "2026-06-10": ["EEC"] }
}
```

**Google authentication tokens** are stored per user at `~/.Student_data/<your-name>/token.json` and refreshed automatically when expired. Legacy slot key formats (e.g. `2026-06-10_14` instead of `2026-06-10_14:00`) are handled automatically for backward compatibility.


## Running Tests

The project includes a full unit test suite covering all modules. Tests use mocking so **no real Google credentials are required**.

```bash
python3 -m unittest test_main.py
```

| Test Class              | What Is Tested                                            |
| ----------------------- | --------------------------------------------------------- |
| `TestBookingHelpers`    | Slot key normalisation and resolution                     |
| `TestSlotChecks`        | Volunteer and student assignment detection                |
| `TestBookingActions`    | `book_slot()` and `volunteer_slot()` end-to-end           |
| `TestCalendarService`   | Slot generation, data cleanup, admin logging              |
| `TestCancelFunctions`   | Student and volunteer cancellation, invalid slot handling |
| `TestClinicHelpers`     | Slot normalisation, role enforcement, print helpers       |
| `TestSlotStatus`        | Display status strings per role                           |
| `TestAvailabilityLogic` | Role-based slot availability logic                        |
| `TestSchedulerViews`    | Summary display and day view output                       |

---

## 📄 License

This project is open-source under the MIT License.
