import os
import json
import datetime

from typing import List, Optional
from functools import wraps
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

try:
    from googleapiclient.errors import HttpError
except ImportError:
    raise ImportError(
        "google client libraries not found, please install using `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`"
    )


def authenticate(func):
    """a decorator who ensures auth before exec method"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            if not self.credentials or not self.credentials.valid:
                self._connect()
            if not self.service:
                self.service = build("calendar", "v3", credentials=self.credentials)
        except Exception as e:
            print(f"an error occurred: {e}")
        return func(self, *args, **kwargs)

    return wrapper


class GoogleCalendarService:

    credentials: Credentials | None = None

    READ_ONLY_SCOPE: str = "https://www.googleapis.com/auth/calendar.readonly"
    WRITE_SCOPE: str = "https://www.googleapis.com/auth/calendar"

    service: Optional[Resource]

    def __init__(
        self,
        scopes: Optional[List[str]] = None,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        calendar_id: str = "main",
        oauth_port: int = 8080,
        allow_update: bool = False,
        **kwargs,
    ):

        self.scopes = scopes or []
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.calendar_id = calendar_id
        self.oauth_port = oauth_port
        self.allow_update = allow_update

        self.credentials = None
        self.service = None

        if not self.scopes:
            self.scopes.append(self.READ_ONLY_SCOPE)
            if self.allow_update:
                self.scopes.append(self.WRITE_SCOPE)

    def _connect(self) -> None:
        if self.credentials and self.credentials.valid:
            return

        token_file = Path(self.token_path or "token.json")
        credentials_file = Path(self.credentials_path or "credentials.json")

        if os.path.exists(token_file):
            self.credentials = Credentials.from_authorized_user_file(
                token_file, scopes=self.scopes
            )

        if not self.credentials or not self.credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, scopes=self.scopes
            )
            self.credentials = flow.run_local_server(port=0)

            with open(token_file, "w") as token:
                token.write(self.credentials.to_json())

    @authenticate
    def find_many_events(
        self,
        limit=10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:

        try:
            params = {
                "calendarId": self.calendar_id,
                "maxResults": min(limit, 100),
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if start_date:
                try:
                    dt = datetime.datetime.fromisoformat(start_date)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    params["timeMin"] = dt.isoformat()
                except ValueError:
                    params["timeMin"] = start_date
            else:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                params["timeMin"] = now
                print(f"no start date provided, using current datetime: {now}")

            if end_date:
                try:
                    dt = datetime.datetime.fromisoformat(end_date)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=datetime.timezone.utc)
                    params["timeMax"] = dt.isoformat()
                except ValueError:
                    params["timeMax"] = end_date

            events = []
            page_token = None

            while True:
                if page_token:
                    params["pageToken"] = page_token

                events_result = self.service.events().list(**params).execute()
                events.extend(events_result.get("items", []))

                if limit and len(events) >= limit:
                    events = events[:limit]
                    break

                page_token = events_result.get("nextPageToken")
                if not page_token:
                    break

            if not events:
                return json.dumps({"message": "no events found"})

            return json.dumps(events)
        except HttpError as error:
            print(f"an error occurred: {error}")
            return json.dumps({"error": f"an error occurred: {error}"})

    @authenticate
    def find_one_event(self, event_id: str) -> str:
        try:
            event = (
                self.service.events()
                .get(calendarId=self.calendar_id, eventId=event_id)
                .execute()
            )
            return json.dumps(event)
        except HttpError as error:
            print(f"an error occurred while fetching event: {error}")
            return json.dumps({"error": f"an error occurred: {error}"})

    @authenticate
    def create_event(self, event_data: dict) -> str:
        """
        Create a new Google Calendar event.

        Args:
            event_data (dict): Event resource body as defined by Google Calendar API.

            Keys mais comuns:
                - summary (str): Título do evento. [Obrigatório]
                - description (str): Texto opcional com detalhes.
                - location (str): Endereço físico ou link (ex: Zoom/Meet).
                - colorId (str): ID da cor do evento (1–11).

                - start (dict): Data/hora de início [Obrigatório]
                    - dateTime (str): Ex: "2025-09-06T10:00:00-03:00"
                    - timeZone (str): Ex: "America/Sao_Paulo"

                - end (dict): Data/hora de término [Obrigatório]
                    - dateTime (str): Ex: "2025-09-06T11:00:00-03:00"
                    - timeZone (str): Ex: "America/Sao_Paulo"

                - attendees (list[dict]): Lista de participantes
                    Ex: [{"email": "pessoa1@email.com"}, {"email": "pessoa2@email.com"}]

                - reminders (dict): Configuração de lembretes
                    - useDefault (bool): Usa os lembretes padrão do calendário.
                    - overrides (list[dict]): Lista de lembretes customizados
                        Ex: [{"method": "email", "minutes": 30},
                             {"method": "popup", "minutes": 10}]

                - recurrence (list[str]): Regras de repetição
                    Ex: ["RRULE:FREQ=WEEKLY;COUNT=10"] (evento semanal por 10 semanas)

        Returns:
            str: JSON string contendo os dados do evento criado ou mensagem de erro.
        """
        try:
            event = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event_data)
                .execute()
            )
            print(f"event #{event.get('id')} created successfully")
            return json.dumps(event)
        except HttpError as error:
            print(f"an error occurred while creating event: {error}")
            return json.dumps({"error": f"an error occurred: {error}"})

    @authenticate
    def update_event(self, event_id: str, updated_data: dict) -> str:
        try:
            event = (
                self.service.events()
                .update(
                    calendarId=self.calendar_id, eventId=event_id, body=updated_data
                )
                .execute()
            )
            print(f"event #{event_id} updated successfully")
            return json.dumps(event)
        except HttpError as error:
            print(f"an error occurred while updating event: {error}")
            return json.dumps({"error": f"an error occurred: {error}"})

    @authenticate
    def remove_event(self, event_id: str) -> str:
        try:
            self.service.events().delete(
                calendarId=self.calendar_id, event_id=event_id
            ).execute()
            print(f"event #{event_id} removed successfully")
            return json.dumps(
                {"success": True, "message": f"event ${event_id} removed successfully"}
            )
        except HttpError as error:
            print(f"an error occurred while deleting event: {error}")
            return json.dumps({"error": f"an error occured: {error}"})
