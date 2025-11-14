# teammanager/interviews/services/google_meet.py
import uuid
from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def _service():
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON, scopes=SCOPES
    )
    # delegated = creds.with_subject(settings.GOOGLE_CALENDAR_DELEGATED_USER)
    # return build("calendar", "v3", credentials=delegated)
    service = build("calendar", "v3", credentials=creds)
    return service

def create_meet(interview):
    service = _service()
    event = {
        "summary": f"Interview – {interview.vacancy.title}",
        "start": {"dateTime": interview.schedule_start.isoformat(), "timeZone": "Africa/Lagos"},
        "end": {"dateTime": interview.schedule_end.isoformat(), "timeZone": "Africa/Lagos"},
        "conferenceData": {
            "createRequest": {
                "requestId": f"int-{interview.id}-{uuid.uuid4()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "attendees": [{"email": u.email} for u in interview.interviewers.all()],
        "reminders": {"useDefault": True},
    }
    created = service.events().insert(
        calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all"
    ).execute()

    interview.google_event_id = created["id"]
    interview.google_meet_link = created.get("hangoutsMeetLink")
    interview.save(update_fields=["google_event_id", "google_meet_link"])