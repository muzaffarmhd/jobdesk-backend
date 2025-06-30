import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import weaviate
from weaviate.classes.query import Filter

# Load environment
load_dotenv()
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Init FastAPI
app = FastAPI()

# CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TF-IDF vectorizer
vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')

# Weaviate client
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_API_KEY)
)
collection = client.collections.get("JobDescription")

# Input model
class Message(BaseModel):
    message: str

@app.post("/chat")
async def chat(msg: Message):
    user_input = msg.message

    all_jobs = collection.query.fetch_objects(limit=100)
    
    job_texts = []
    job_objects = []
    
    for obj in all_jobs.objects:
        props = obj.properties
        job_text = f"{props['role']} {props['experience']} {' '.join(props['technicalSkills'])} {' '.join(props['softSkills'])} {' '.join(props['responsibilities'])} {' '.join(props['tools'])} {props['education']} {props['industry']}"
        job_texts.append(job_text)
        job_objects.append(obj)
    
    if job_texts:
        tfidf_matrix = vectorizer.fit_transform(job_texts)
        user_vector = vectorizer.transform([user_input])
        
        similarities = cosine_similarity(user_vector, tfidf_matrix).flatten()
        
        top_indices = np.argsort(similarities)[-3:][::-1]
        top_jobs = [job_objects[i] for i in top_indices if similarities[i] > 0]
    else:
        top_jobs = []

    context = ""
    for obj in top_jobs:
        props = obj.properties
        context += f"""
Role: {props['role']}
Experience: {props['experience']}
Technical Skills: {', '.join(props['technicalSkills'])}
Soft Skills: {', '.join(props['softSkills'])}
Responsibilities: {', '.join(props['responsibilities'])}
Tools: {', '.join(props['tools'])}
Education: {props['education']}
Industry: {props['industry']}
---
"""

    prompt = f"""
You are JobDesk, a friendly career assistant. 

User Message: {user_input}

Instructions:
- If the user is just greeting you, respond with a friendly greeting and ask how you can help with their job search, do not mention about existing jds
- If the user asks about jobs/careers, use the job descriptions below to help
- Keep responses concise and relevant to what the user actually asked

{context if context.strip() else "No specific job context needed for this query."}

Response:
"""

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4
        }
    )

    if response.status_code == 200:
        content = response.json()
        reply = content["choices"][0]["message"]["content"]
    else:
        reply = "⚠️ Error: Could not fetch response from LLM."

    return {"response": reply}
