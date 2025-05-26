from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.models import models
from app.schemas import schemas
from app.crud import crud
from app.services.openai_service import generate_job_description, stream_job_description
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/", response_model=schemas.JobPosting)
def create_job_posting(job: schemas.JobPostingCreate, db: Session = Depends(get_db)):
    # Verify company exists
    company = db.query(models.Company).filter(models.Company.id == job.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    db_job = models.JobPosting(**job.dict())
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

@router.get("/", response_model=List[schemas.JobPosting])
def read_job_postings(
    skip: int = 0,
    limit: int = 100,
    company_id: Optional[int] = None,
    title: Optional[str] = None,
    location: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.JobPosting)
    
    if company_id:
        query = query.filter(models.JobPosting.company_id == company_id)
    if title:
        query = query.filter(models.JobPosting.title.ilike(f"%{title}%"))
    if location:
        query = query.filter(models.JobPosting.location.ilike(f"%{location}%"))
    
    return query.offset(skip).limit(limit).all()

#jobs/6
@router.get("/{job_id}", response_model=schemas.JobPosting)
def read_job_posting(job_id: int, db: Session = Depends(get_db)):
    db_job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return db_job

@router.put("/{job_id}", response_model=schemas.JobPosting)
def update_job_posting(
    job_id: int,
    job: schemas.JobPostingUpdate,
    db: Session = Depends(get_db)
):
    db_job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    # If company_id is being updated, verify the new company exists
    if job.company_id and job.company_id != db_job.company_id:
        company = db.query(models.Company).filter(models.Company.id == job.company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
    
    for key, value in job.dict(exclude_unset=True).items():
        setattr(db_job, key, value)
    
    db.commit()
    db.refresh(db_job)
    return db_job

@router.delete("/{job_id}")
def delete_job_posting(job_id: int, db: Session = Depends(get_db)):
    db_job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    db.delete(db_job)
    db.commit()
    return {"message": "Job posting deleted successfully"}

@router.post("/{job_id}/description", response_model=schemas.JobDescriptionResponse)
async def generate_job_description_endpoint(
    job_id: int = Path(..., description="The ID of the job posting"),
    request: schemas.JobDescriptionRequest = None,
    db: Session = Depends(get_db)
):
    """
    Generate a job description using OpenAI's GPT model.
    """
    # Get job posting and company information
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    company = crud.get_company(db, job.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Generate job description
    description = generate_job_description(
        job_title=job.title,
        company_name=company.name,
        required_tools=request.required_tools
    )

    # Update job posting with new description
    job.description = description
    db.commit()
    db.refresh(job)

    return schemas.JobDescriptionResponse(
        job_id=job.id,
        description=description,
        company_name=company.name,
        job_title=job.title
    )

@router.post("/{job_id}/description/stream")
async def stream_job_description_endpoint(
    job_id: int = Path(..., description="The ID of the job posting"),
    request: schemas.JobDescriptionRequest = None,
    db: Session = Depends(get_db)
):
    """
    Stream the job description generation process.
    """
    # Get job posting and company information
    job = crud.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    
    company = crud.get_company(db, job.company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    async def generate():
        full_description = ""
        async for chunk in stream_job_description(
            job_title=job.title,
            company_name=company.name,
            required_tools=request.required_tools
        ):
            full_description += chunk
            yield chunk

        # Update job posting with the complete description
        job.description = full_description
        db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    ) 