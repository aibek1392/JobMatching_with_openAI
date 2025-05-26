from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models import models
from app.schemas import schemas

router = APIRouter()

@router.post("/", response_model=schemas.Application)
def create_application(application: schemas.ApplicationCreate, db: Session = Depends(get_db)):
    # Verify job posting exists
    job = db.query(models.JobPosting).filter(models.JobPosting.id == application.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    db_application = models.Application(**application.dict())
    db.add(db_application)
    db.commit()
    db.refresh(db_application)
    return db_application

@router.get("/", response_model=List[schemas.Application])
def read_applications(
    skip: int = 0,
    limit: int = 100,
    job_id: Optional[int] = None,
    candidate_id: Optional[str] = None,
    email: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Application)
    
    if job_id:
        query = query.filter(models.Application.job_id == job_id)
    if candidate_id:
        query = query.filter(models.Application.candidate_id == candidate_id)
    if email:
        query = query.filter(models.Application.email == email)
    if status:
        query = query.filter(models.Application.status == status)
    
    return query.offset(skip).limit(limit).all()

@router.get("/{application_id}", response_model=schemas.Application)
def read_application(application_id: int, db: Session = Depends(get_db)):
    db_application = db.query(models.Application).filter(models.Application.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return db_application

@router.put("/{application_id}", response_model=schemas.Application)
def update_application(
    application_id: int,
    application: schemas.ApplicationUpdate,
    db: Session = Depends(get_db)
):
    db_application = db.query(models.Application).filter(models.Application.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # If job_id is being updated, verify the new job exists
    if application.job_id and application.job_id != db_application.job_id:
        job = db.query(models.JobPosting).filter(models.JobPosting.id == application.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job posting not found")
    
    for key, value in application.dict(exclude_unset=True).items():
        setattr(db_application, key, value)
    
    db.commit()
    db.refresh(db_application)
    return db_application

@router.delete("/{application_id}")
def delete_application(application_id: int, db: Session = Depends(get_db)):
    db_application = db.query(models.Application).filter(models.Application.id == application_id).first()
    if db_application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    
    db.delete(db_application)
    db.commit()
    return {"message": "Application deleted successfully"} 