import os
import json
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

import weaviate
from weaviate.classes.config import Configure, Property, DataType

# Load environment variables
load_dotenv()
WEAVIATE_URL = os.getenv("WEAVIATE_URL")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY")

# Load sentence-transformer model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Setup Weaviate client
client = weaviate.connect_to_weaviate_cloud(
    cluster_url=WEAVIATE_URL,
    auth_credentials=weaviate.auth.AuthApiKey(WEAVIATE_API_KEY)
)

# Define schema if not exists
class_name = "JobDescription"

if not client.collections.exists(class_name):
    client.collections.create(
        name=class_name,
        properties=[
            Property(name="role", data_type=DataType.TEXT),
            Property(name="experience", data_type=DataType.TEXT),
            Property(name="technicalSkills", data_type=DataType.TEXT_ARRAY),
            Property(name="softSkills", data_type=DataType.TEXT_ARRAY),
            Property(name="responsibilities", data_type=DataType.TEXT_ARRAY),
            Property(name="tools", data_type=DataType.TEXT_ARRAY),
            Property(name="education", data_type=DataType.TEXT),
            Property(name="industry", data_type=DataType.TEXT),
        ],
        vectorizer_config=Configure.Vectorizer.none(),
    )

# Get the collection
collection = client.collections.get(class_name)

# Load job data
with open("cleaned_json.json", "r", encoding="utf-8") as f:
    jobs = json.load(f)

# Upload jobs
for i, job in enumerate(jobs):
    text = f"""
    Role: {job['role']}
    Experience: {job['Experience Level']}
    Technical Skills: {', '.join(job['Technical Skills'])}
    Soft Skills: {', '.join(job['Soft Skills'])}
    Responsibilities: {', '.join(job['Key Responsibilities'])}
    Tools: {', '.join(job['Tools & Technologies'])}
    Education: {job['Education Requirements']}
    Industry: {job['Industry/Domain']}
    """

    # Generate embedding
    vector = model.encode(text)

    # Build object
    obj = {
        "role": job["role"],
        "experience": job["Experience Level"],
        "technicalSkills": job["Technical Skills"],
        "softSkills": job["Soft Skills"],
        "responsibilities": job["Key Responsibilities"],
        "tools": job["Tools & Technologies"],
        "education": job["Education Requirements"],
        "industry": job["Industry/Domain"],
    }

    # Insert with vector
    collection.data.insert(properties=obj, vector=vector)
    print(f"✅ Uploaded job {i + 1}/{len(jobs)}")

print("🎉 All job descriptions uploaded to Weaviate Cloud!")
client.close()