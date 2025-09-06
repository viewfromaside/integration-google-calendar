from __future__ import print_function
import datetime
from googlecalendar import GoogleCalendarService


def main():
    calendar_service = GoogleCalendarService(
        credentials_path="./credentials.json",
        token_path="./token.json",
        calendar_id="primary",
        oauth_port=8080,
        allow_update=True,
    )

    event_data = {
        "summary": "aniversario do meu gato",
        "description": "nome dele eh tchutchuco",
        "start": {
            "dateTime": "2025-09-06T10:00:00-03:00",
            "timeZone": "America/Sao_Paulo",
        },
        "end": {
            "dateTime": "2025-09-06T11:00:00-03:00",
            "timeZone": "America/Sao_Paulo",
        },
    }

    created_event = calendar_service.create_event(event_data)
    print("event created:", created_event)

    event_id = None
    try:
        event_id = eval(created_event).get("id")
    except Exception:
        pass

    events = calendar_service.find_many_events(limit=5)
    print("future events:", events)

    if event_id:
        event = calendar_service.find_one_event(event_id)
        print("event found by ID:", event)

    if event_id:
        deleted = calendar_service.remove_event(event_id)
        print("event removed:", deleted)

    events_after_delete = calendar_service.find_many_events(limit=5)
    print("events post removed one:", events_after_delete)


if __name__ == "__main__":
    main()
