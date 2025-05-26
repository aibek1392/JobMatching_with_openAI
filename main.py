from fastapi import FastAPI, Query, Path, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os
from app.api.endpoints import companies
from datetime import datetime
import openai

# Load environment variables
load_dotenv()

# SQLAlchemy setup 
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("Database URL format check:")
if DATABASE_URL:
    # Mask the password for security
    masked_url = DATABASE_URL.replace(DATABASE_URL.split('@')[0].split(':')[-1], '****')
    print(f"Found DATABASE_URL: {masked_url}")
else:
    print("DATABASE_URL not found in environment variables")

try:
    engine = create_engine(DATABASE_URL)
    # Test the connection
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Successfully connected to the database!")
except Exception as e:
    print(f"Error connecting to the database: {str(e)}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()

# This is our data model - what an application looks like
class Candidate(BaseModel):
    candidate_id: str 
    name: str 
    email: str 
    job_id: str | None = None

class JobDescriptionRequest(BaseModel):
    required_tools: List[str]

# This is our "database" - just a list in memory - cache memory
applications: List[Candidate] = []

#creating a db connection session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()    
    

@app.get("/jobs")
def get_all_job_postings(db: Session = Depends(get_db)):
    result = db.execute(text('SELECT * FROM "JobPosting"'))
    
    rows = result.fetchall()

    #format each row as a String
    output = []
    for row in rows:
        output.append(str(dict(row._mapping)))

    return output    
    

@app.post("/jobs/{job_id}/description")
def generate_job_description(
    job_id: int,
    request: JobDescriptionRequest,
    db: Session = Depends(get_db)
):
    # Get job details from database
    result = db.execute(
        text('SELECT * FROM "JobPosting" WHERE id = :job_id'),
        {"job_id": job_id}
    )
    job = result.fetchone()
    
    if not job:
        return {"error": "Job not found"}
    
    # Get company details
    company_result = db.execute(
        text('SELECT * FROM "Company" WHERE id = :company_id'),
        {"company_id": job.company_id}
    )
    company = company_result.fetchone()
    
    if not company:
        return {"error": "Company not found"}
    
    # Prepare the prompt for GPT
    prompt = f"""Generate a detailed job description for a {job.title} position at {company.name} in {job.location}.
    Required tools and technologies: {', '.join(request.required_tools)}
    
    The description should include:
    1. A compelling introduction
    2. Key responsibilities
    3. Required qualifications
    4. Preferred qualifications
    5. Company benefits and culture
    """
    
    try:
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Generate description using GPT-4
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional job description writer."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        description = response.choices[0].message.content
        
        # Update the job posting with the generated description
        db.execute(
            text('UPDATE "JobPosting" SET description = :description WHERE id = :job_id'),
            {"description": description, "job_id": job_id}
        )
        db.commit()
        
        return {
            "job_id": job_id,
            "description": description,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        return {"error": f"Failed to generate description: {str(e)}"}

@app.post("/applications")
def postApplications(candidate: Candidate):
    #input sanitization --> if the email fits the format or no? 
    #name is at least 2 words
    #does this jobId already in the cache? if yes, update it. if no insert
    applications.append(candidate)
    return {
        "status": "success",
        "message": f"Application submitted for {candidate.name}"
    }

@app.get("/applications")
def getApplication(
    company_name: str = Query(None, description="optional query param for company name"),
    candidate_email: str = Query(None, description="optional query param for candidate email")
):
    if company_name:
        return {
            "status": "success",
            "message": f"Here is your application for {company_name}"
        }
    elif candidate_email:
        return {
            "status": "success",
            "message": f"Here is your application for {candidate_email}"
        }
    else:
        return {
            "status": "success",
            "message": "Here are all of your applications"
        }

@app.get("/applications/{candidate_id}")
def getApplicationById(candidate_id: str):
    for app in applications:
        if app.candidate_id == candidate_id:
            return {
                "status": "success",
                "message": f"Application found for candidate ID: {candidate_id}"
            }
    return {
        "status": "success",
        "message": "Application not found"
    }

@app.put("/applications/{candidate_id}")
def putApplications(
    candidate_id: str = Path(..., description="The ID of the candidate to update"),
    email: str = Query(None, description="New email address"),
    job_id: str = Query(None, description="New job ID")
):
    for app in applications:
        if app.candidate_id == candidate_id:
            if email:
                app.email = email
                return {
                    "status": "success",
                    "message": f"Email updated to {email}"
                }
            if job_id:
                app.job_id = job_id
                return {
                    "status": "success",
                    "message": f"Job ID updated to {job_id}"
                }
    return {
        "status": "success",
        "message": "Application not found"
    }

@app.delete("/applications/{candidate_id}")
def deleteApplication(candidate_id: str):
    for i, app in enumerate(applications):
        if app.candidate_id == candidate_id:
            applications.pop(i)
            return {
                "status": "success",
                "message": f"Application for {candidate_id} has been deleted"
            }
    return {
        "status": "success",
        "message": "Application not found"
    }

# Add this line after creating the FastAPI app
app.include_router(companies.router, prefix="/companies", tags=["companies"])