from pydantic import BaseModel, HttpUrl, EmailStr
from typing import Optional, List
from datetime import datetime

# Company Schemas
class CompanyBase(BaseModel):
    name: str #required
    industry: Optional[str] = None
    url: Optional[str] = None
    headcount: Optional[int] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    isPublic: Optional[bool] = False

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    name: Optional[str] = None #optional

class Company(CompanyBase):
    id: int

    class Config:
        from_attributes = True

# JobPosting Schemas
class JobPostingBase(BaseModel):
    company_id: int
    title: str
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None

class JobPostingCreate(JobPostingBase):
    pass

class JobPostingUpdate(JobPostingBase):
    company_id: Optional[int] = None
    title: Optional[str] = None

class JobPosting(JobPostingBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Job Description Generation Schemas
class JobDescriptionRequest(BaseModel):
    required_tools: List[str]

class JobDescriptionResponse(BaseModel):
    job_id: int
    description: str
    company_name: str
    job_title: str

# Application Schemas
class ApplicationBase(BaseModel):
    job_id: int
    candidate_id: str
    name: str
    email: EmailStr
    status: str = "Pending"

class ApplicationCreate(ApplicationBase):
    pass

class ApplicationUpdate(ApplicationBase):
    job_id: Optional[int] = None
    candidate_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None

class Application(ApplicationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True 