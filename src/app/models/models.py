from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

class Company(Base):
    __tablename__ = "Company"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    industry = Column(String)
    url = Column(String)
    headcount = Column(Integer)
    country = Column(String)
    state = Column(String)
    city = Column(String)
    isPublic = Column(Boolean, default=False)

    job_postings = relationship("JobPosting", back_populates="company")

class JobPosting(Base):
    __tablename__ = "JobPosting"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    company_id = Column(Integer, ForeignKey("Company.id"))
    location = Column(String)
    description = Column(String)
    requirements = Column(String)
    salary_range = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="job_postings")
    applications = relationship("Application", back_populates="job")

class Application(Base):
    __tablename__ = "Application"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String, index=True)
    name = Column(String)
    email = Column(String, index=True)
    job_id = Column(Integer, ForeignKey("JobPosting.id"))
    status = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    job = relationship("JobPosting", back_populates="applications") 