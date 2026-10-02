from pydantic import BaseModel


class ScheduleCreate(BaseModel):
    name: str
    hour: int
    minute: int
    enabled: bool = True
    description: str = ""
    search_text: str = ""
    send_to_telegram: bool = True


class ScheduleUpdate(BaseModel):
    name: str | None = None
    hour: int | None = None
    minute: int | None = None
    enabled: bool | None = None
    description: str | None = None
    search_text: str | None = None
    send_to_telegram: bool | None = None
    last_run_date: str | None = None
    last_result: str | None = None
