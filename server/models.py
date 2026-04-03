from typing import Optional
from pydantic import BaseModel


class SingleEmail(BaseModel):
    email: str
    name: str
    html: Optional[str] = None


class BatchContact(BaseModel):
    id: Optional[str] = None
    email: str
    name: str


class BatchEmail(BaseModel):
    contacts: list[BatchContact]
    html: Optional[str] = None


class TemplateUpdate(BaseModel):
    html: str
