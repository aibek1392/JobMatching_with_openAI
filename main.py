from fastapi import FastAPI, Query, Path, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, text
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv
import os
from app.api.endpoints import companies
from datetime import datetime
import openai
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate
import json

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React app's address
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# This is our data model - what an application looks like
class Candidate(BaseModel):
    candidate_id: str 
    name: str 
    email: str 
    job_id: str | None = None

# Pydantic models for structured output
class JobDescriptionComponents(BaseModel):
    title: str = Field(description="The job title")
    overview: str = Field(description="A brief 2-3 sentence overview of the role")
    responsibilities: List[str] = Field(description="4-6 key responsibilities of the role")
    required_skills: List[str] = Field(description="3-5 required technical skills")
    qualifications: List[str] = Field(description="2-3 key qualifications")
    benefits: List[str] = Field(description="2-3 key benefits of the role")
    company_culture: Optional[str] = Field(description="Description of company culture and work environment")

class JobDescriptionRequest(BaseModel):
    required_tools: List[str]
    company_culture: Optional[str] = None

# This is our "database" - just a list in memory - cache memory
applications: List[Candidate] = []

#creating a db connection session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()    

# Initialize LangChain chat model
def init_chat_model():
    return ChatOpenAI(
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=500,
        frequency_penalty=0.1,
        presence_penalty=0.1
    )

# Create prompt templates
SYSTEM_TEMPLATE = """You are a professional job description writer with expertise in technical roles. 
Generate a structured job description following these guidelines:

1. Structure:
   - Start with a brief 2-3 sentence overview
   - List 4-6 key responsibilities
   - List 3-5 required skills
   - List 2-3 key qualifications
   - End with 2-3 key benefits
   - Include company culture if provided

2. Content Rules:
   - Be specific about technical requirements
   - Use clear, professional language
   - Avoid generic phrases
   - Focus on measurable skills
   - Include specific tools and technologies

3. Formatting:
   - Use clear, concise language
   - Maintain professional tone
   - Be specific and actionable

4. Restrictions:
   - No salary information
   - No discriminatory language
   - No vague requirements
   - No marketing language

{format_instructions}"""

HUMAN_TEMPLATE = """Write a job description for a {job_title} position at {company_name} in {location}.

Required Technical Tools: {required_tools}

Company Culture: {company_culture}

Additional Context:
- Company: {company_name}
- Location: {location}
- Role: {job_title}"""

# Create the prompt template
def create_prompt_template():
    system_message_prompt = SystemMessagePromptTemplate.from_template(SYSTEM_TEMPLATE)
    human_message_prompt = HumanMessagePromptTemplate.from_template(HUMAN_TEMPLATE)
    return ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])

@app.get("/jobs")
def get_all_job_postings(db: Session = Depends(get_db)):
    result = db.execute(text('SELECT * FROM "JobPosting"'))
    rows = result.fetchall()
    output = []
    for row in rows:
        # Convert the row to a dictionary and handle datetime objects
        job_dict = dict(row._mapping)
        # Convert datetime objects to ISO format strings
        if job_dict.get('created_at'):
            job_dict['created_at'] = job_dict['created_at'].isoformat()
        if job_dict.get('updated_at'):
            job_dict['updated_at'] = job_dict['updated_at'].isoformat()
        output.append(job_dict)
    return output

@app.get("/jobs/{job_id}")
def get_job_posting(job_id: int, db: Session = Depends(get_db)):
    result = db.execute(
        text('SELECT * FROM "JobPosting" WHERE id = :job_id'),
        {"job_id": job_id}
    )
    job = result.fetchone()
    
    if not job:
        return {"error": "Job not found"}
    
    return dict(job._mapping)

@app.post("/jobs/{job_id}/description/stream")
async def generate_job_description(
    job_id: int,
    request: JobDescriptionRequest,
    db: Session = Depends(get_db)
):
    try:
        # Get job details from database
        result = db.execute(
            text('SELECT * FROM "JobPosting" WHERE id = :job_id'),
            {"job_id": job_id}
        )
        job = result.fetchone()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get company details
        company_result = db.execute(
            text('SELECT * FROM "Company" WHERE id = :company_id'),
            {"company_id": job.company_id}
        )
        company = company_result.fetchone()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        async def generate():
            try:
                # Initialize LangChain components
                chat_model = init_chat_model()
                prompt_template = create_prompt_template()
                output_parser = PydanticOutputParser(pydantic_object=JobDescriptionComponents)

                # Format the prompt
                formatted_prompt = prompt_template.format_messages(
                    format_instructions=output_parser.get_format_instructions(),
                    job_title=job.title,
                    company_name=company.name,
                    location=job.location,
                    required_tools=", ".join(request.required_tools),
                    company_culture=request.company_culture or "Not specified"
                )

                # Stream the response
                async for chunk in chat_model.astream(formatted_prompt):
                    if chunk.content:
                        # Send each chunk as it arrives
                        yield f"data: {json.dumps({'chunk': chunk.content})}\n\n".encode('utf-8')

                # Get the final response
                response = await chat_model.ainvoke(formatted_prompt)
                job_description = output_parser.parse(response.content)

                # Send the final complete response
                yield f"data: {job_description.json()}\n\n".encode('utf-8')

                # Update the job posting with the complete description
                formatted_description = f"""
Title: {job_description.title}

Overview:
{job_description.overview}

Responsibilities:
{chr(10).join(f"• {resp}" for resp in job_description.responsibilities)}

Required Skills:
{chr(10).join(f"• {skill}" for skill in job_description.required_skills)}

Qualifications:
{chr(10).join(f"• {qual}" for qual in job_description.qualifications)}

Benefits:
{chr(10).join(f"• {benefit}" for benefit in job_description.benefits)}

Company Culture:
{job_description.company_culture if job_description.company_culture else "Not specified"}
"""

                # Save to database
                db.execute(
                    text('UPDATE "JobPosting" SET description = :description WHERE id = :job_id'),
                    {"description": formatted_description, "job_id": job_id}
                )
                db.commit()

            except Exception as e:
                error_message = f"data: {json.dumps({'error': str(e)})}\n\n".encode('utf-8')
                yield error_message

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating job description: {str(e)}")

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
    for app in applications:
        if app.candidate_id == candidate_id:
            applications.remove(app)
            return {
                "status": "success",
                "message": f"Application deleted for candidate ID: {candidate_id}"
            }
    return {
        "status": "success",
        "message": "Application not found"
    }

# Add this line after creating the FastAPI app
app.include_router(companies.router, prefix="/companies", tags=["companies"])