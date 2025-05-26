from openai import OpenAI
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_job_description(
    job_title: str,
    company_name: str,
    required_tools: List[str]
) -> str:
    """
    Generate a job description using OpenAI's GPT model.
    """
    prompt = f"""Generate a detailed job description for a {job_title} position at {company_name}.
    The candidate should be proficient in the following tools and technologies: {', '.join(required_tools)}.
    
    The description should include:
    1. A brief overview of the role
    2. Key responsibilities
    3. Required skills and qualifications
    4. Preferred experience
    5. What makes this role exciting
    
    Format the response in a professional and engaging way."""

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a professional HR writer who creates engaging and detailed job descriptions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )

    return response.choices[0].message.content

async def stream_job_description(
    job_title: str,
    company_name: str,
    required_tools: List[str]
):
    """
    Stream the job description generation process.
    """
    prompt = f"""Generate a detailed job description for a {job_title} position at {company_name}.
    The candidate should be proficient in the following tools and technologies: {', '.join(required_tools)}.
    
    The description should include:
    1. A brief overview of the role
    2. Key responsibilities
    3. Required skills and qualifications
    4. Preferred experience
    5. What makes this role exciting
    
    Format the response in a professional and engaging way."""

    stream = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": "You are a professional HR writer who creates engaging and detailed job descriptions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000,
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content 