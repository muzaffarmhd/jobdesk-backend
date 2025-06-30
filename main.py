import os
import secrets
import json
import requests
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from dotenv import load_dotenv
from supabase_client import supabase
from gotrue.types import UserAttributes

# Lightweight transformer setup
from transformers import AutoTokenizer, AutoModel
import torch
import weaviate

# Load .env variables
load_dotenv()

# --- Env Vars ---
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- FastAPI App ---
app = FastAPI(title="Job Desc AI API - Final Backend", version="5.0.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Email Config ---
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_USERNAME"),
    MAIL_FROM_NAME="Job Desc AI",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False
)

# --- Models ---
class UserCredentials(BaseModel):
    email: EmailStr
    password: str

class EmailBody(BaseModel):
    email: EmailStr

class UpdatePasswordWithToken(BaseModel):
    token: str
    new_password: str

class Conversation(BaseModel):
    id: str
    title: str
    created_at: str

class NewConversation(BaseModel):
    title: str

class Message(BaseModel):
    id: str
    role: str
    content: str
    created_at: str

class NewMessage(BaseModel):
    content: str

# --- Email Helper ---
async def send_custom_email(to_email: str, subject: str, link: str):
    html_content = f"""<h3>Password Reset Request</h3>
    <p>You requested a password reset. Click the link below (valid for 1 hour):</p>
    <p><a href="{link}" target="_blank">Reset Your Password</a></p>"""
    message = MessageSchema(
        subject=subject,
        recipients=[to_email],
        body=html_content,
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    try:
        await fm.send_message(message)
    except Exception as e:
        print(f"Failed to send reset email: {e}")

# --- Auth Helpers ---
def get_user_from_token(token: str):
    try:
        user_response = supabase.auth.get_user(token)
        return user_response.user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

# --- Lightweight Embedding Model Setup ---
tokenizer = AutoTokenizer.from_pretrained("intfloat/e5-small", trust_remote_code=True)
model = AutoModel.from_pretrained("intfloat/e5-small", trust_remote_code=True)

def get_embedding(text: str):
    inputs = tokenizer(f"query: {text}", return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        model_output = model(**inputs)
    embeddings = model_output.last_hidden_state.mean(dim=1)
    return embeddings[0].tolist()

# --- Weaviate Client Setup ---
weaviate_client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_API_KEY)
)
collection = weaviate_client.collections.get("JobDescription")

# --- Auth Routes ---
@app.post("/signup")
async def signup(credentials: UserCredentials):
    try:
        supabase.auth.admin.create_user({
            "email": credentials.email,
            "password": credentials.password,
            "email_confirm": True
        })
        supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        return {"message": "Signup successful! You can now log in or reset password."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login", tags=["Authentication"])
async def login(credentials: UserCredentials):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        return {"access_token": response.session.access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid login credentials: {e}")

@app.post("/reset-password", tags=["Authentication"])
async def request_password_reset(body: EmailBody):
    try:
        list_users_response = supabase.auth.admin.list_users()
        user = next((u for u in list_users_response if u.email == body.email), None)
        if not user:
            return {"message": "If an account with that email exists, a password reset link has been sent."}

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        supabase.table("password_reset_tokens").insert({
            "user_id": user.id,
            "token": token,
            "expires_at": expires_at.isoformat()
        }).execute()

        reset_link = f"http://localhost:5173/update-password?token={token}"
        await send_custom_email(
            to_email=body.email,
            subject="Your Job Desc AI Password Reset Link",
            link=reset_link
        )
        return {"message": "If an account with that email exists, a password reset link has been sent."}
    except Exception as e:
        return {"message": "An error occurred. Please try again later."}

@app.post("/update-password", tags=["Authentication"])
async def update_password_with_token(credentials: UpdatePasswordWithToken):
    try:
        response = supabase.table("password_reset_tokens").select("*").eq("token", credentials.token).single().execute()
        token_data = response.data
        if not token_data:
            raise HTTPException(status_code=400, detail="Invalid or expired token.")

        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if expires_at < datetime.now(timezone.utc):
            supabase.table("password_reset_tokens").delete().eq("id", token_data['id']).execute()
            raise HTTPException(status_code=400, detail="Token has expired.")

        user_id = token_data['user_id']
        supabase.auth.admin.update_user_by_id(user_id, attributes={"password": credentials.new_password})
        supabase.table("password_reset_tokens").delete().eq("id", token_data['id']).execute()

        return {"message": "Password updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid token or error updating password.")

# --- User Profile ---
@app.get("/user", tags=["User Management"])
async def get_user_profile(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[-1]
    user = get_user_from_token(token)
    return user

# --- Conversations ---
@app.get("/conversations", tags=["Conversations"], response_model=List[Conversation])
async def get_conversations(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[-1]
    user = get_user_from_token(token)
    try:
        supabase.auth.set_session(access_token=token, refresh_token="dummy")
        response = supabase.table("conversations").select("id, title, created_at").eq("user_id", user.id).order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.post("/conversations", tags=["Conversations"], response_model=Conversation)
async def create_conversation(new_convo: NewConversation, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[-1]
    user = get_user_from_token(token)
    try:
        supabase.auth.set_session(access_token=token, refresh_token="dummy")
        response = supabase.table("conversations").insert({"user_id": user.id, "title": new_convo.title}).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.get("/conversations/{conversation_id}/messages", tags=["Conversations"], response_model=List[Message])
async def get_messages(conversation_id: str, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[-1]
    user = get_user_from_token(token)
    try:
        supabase.auth.set_session(access_token=token, refresh_token="dummy")
        check = supabase.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user.id).single().execute()
        if not check.data:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied.")
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@app.post("/conversations/{conversation_id}/messages", tags=["Conversations"], response_model=Message)
async def add_message(conversation_id: str, new_message: NewMessage, authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[-1]
    user = get_user_from_token(token)
    supabase.auth.set_session(access_token=token, refresh_token="dummy")

    owner_check = supabase.table("conversations").select("id").eq("id", conversation_id).eq("user_id", user.id).single().execute()
    if not owner_check.data:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    try:
        supabase.table("messages").insert({"conversation_id": conversation_id, "role": "user", "content": new_message.content}).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save user message: {e}")

    vector = get_embedding(new_message.content)
    results = collection.query.near_vector(near_vector=vector, limit=3)

    context = ""
    for obj in results.objects:
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

User Message: {new_message.content}

Instructions:
- If the user is just greeting you, respond with a friendly greeting and ask how you can help with their job search.
- If the user asks about jobs/careers, use the job descriptions below to help.
- Keep responses concise and relevant to what the user actually asked.

{context if context.strip() else "No specific job context needed for this query."}

Response:
"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4
            }
        )
        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
        else:
            reply = "⚠️ Error: Could not fetch response from LLM."
    except Exception as e:
        print(f"LLM error: {e}")
        reply = "⚠️ Error: Could not generate response at the moment."

    try:
        ai_response = supabase.table("messages").insert({"conversation_id": conversation_id, "role": "assistant", "content": reply}).execute()
        return ai_response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save AI message: {e}")
