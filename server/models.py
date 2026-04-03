from typing import Optional
from pydantic import BaseModel, EmailStr


class SingleEmail(BaseModel):
    email: EmailStr
    name: str
    html: Optional[str] = None


class BatchContact(BaseModel):
    id: Optional[str] = None
    email: EmailStr
    name: str


class BatchEmail(BaseModel):
    contacts: list[BatchContact]
    html: Optional[str] = None


class TemplateUpdate(BaseModel):
    html: str
