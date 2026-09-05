from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field


class ReportColumnRead(BaseModel):
    key: str
    label: str


class ReportDefinitionRead(BaseModel):
    id: str
    name: str
    description: str
    filters: list[str]
    """Which of ReportFilterParams' fields this report actually uses — lets
    the frontend render only the relevant filter inputs per report."""


class ReportResultRead(BaseModel):
    report_id: str
    title: str
    generated_at: datetime
    generated_by: str
    filters_applied: dict[str, str]
    columns: list[ReportColumnRead]
    rows: list[dict]
    row_count: int
    truncated: bool
    """True if the underlying data exceeded the row cap and this result was cut short."""


class ReportEmailRequest(BaseModel):
    recipient_emails: list[EmailStr] = Field(min_length=1, max_length=20)
    format: str = Field(default="pdf", pattern="^(pdf|xlsx|csv)$")
    message: str | None = Field(default=None, max_length=1000, description="Optional note included in the email body")
    # Filters, mirrored from ReportResultRead's query params so the emailed
    # file matches exactly what the requester was looking at on screen.
    date_from: date | None = None
    date_to: date | None = None
    warehouse_id: str | None = None
    category_id: str | None = None
    status: str | None = None
    asset_id: str | None = None
    entity_type: str | None = None
    action: str | None = None
