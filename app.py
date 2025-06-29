from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import weaviate
from dotenv import load_dotenv
import os

load_dotenv()

# Load model and connect to Weaviate
model = SentenceTransformer("all-MiniLM-L6-v2")
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=os.getenv("WEAVIATE_URL"),
    auth_credentials=weaviate.auth.AuthApiKey(os.getenv("WEAVIATE_API_KEY"))
)
collection = client.collections.get("JobDescription")

app = FastAPI()

class Query(BaseModel):
    message: str

@app.post("/query")
def query_jobs(q: Query):
    vector = model.encode(q.message)
    results = collection.query.near_vector(vector=vector, limit=5)

    return {
        "results": [
            {
                "role": obj.properties.get("role"),
                "experience": obj.properties.get("experience"),
                "industry": obj.properties.get("industry")
            } for obj in results.objects
        ]
    }
