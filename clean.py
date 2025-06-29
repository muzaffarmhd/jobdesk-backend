import json
import os
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class JobDescriptionConverter:
    def __init__(self):
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url = "https://openrouter.ai/api/v1/chat/completions"

        if not self.openrouter_key:
            raise ValueError("OPENROUTER_API_KEY must be set in .env file")

    def call_openrouter_mistral(self, prompt: str) -> Optional[str]:
        if not self.openrouter_key:
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "mistralai/mistral-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 4096
            }

            response = requests.post(self.openrouter_base_url, headers=headers, json=data)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"OpenRouter API error: {e}")
            return None

    def extract_job_fields(self, job_description: str) -> Optional[str]:
        prompt = f"""
Extract information from this job description and return ONLY a valid JSON object.

Job Description:
{job_description}

Extract these fields:
- Experience Level: Extract years of experience required (e.g., "2-4 years", "5+ years", "Entry level", etc.)
- Technical Skills: List specific technical skills, programming languages, frameworks, methodologies
- Soft Skills: List soft skills like communication, leadership, teamwork, problem-solving
- Key Responsibilities: Main job duties and responsibilities 
- Tools & Technologies: Specific tools, platforms, software, cloud services mentioned
- Education Requirements: Required education or "Not explicitly mentioned"
- Industry/Domain: Industry sector (e.g., "Manufacturing", "Finance", "Healthcare", "Technology", etc.)

Return ONLY this JSON format with no additional text:
{{
  "Experience Level": "string",
  "Technical Skills": ["skill1", "skill2", "skill3"],
  "Soft Skills": ["skill1", "skill2"],
  "Key Responsibilities": ["responsibility1", "responsibility2"],
  "Tools & Technologies": ["tool1", "tool2", "tool3"],
  "Education Requirements": "string", 
  "Industry/Domain": "string"
}}

IMPORTANT: Return ONLY the JSON object, no markdown formatting, no explanations.
"""
        return self.call_openrouter_mistral(prompt)

    def parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        if not response:
            return None

        try:
            response = response.strip()

            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip() if end != -1 else response[start:].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip() if end != -1 else response[start:].strip()

            first_brace = response.find("{")
            last_brace = response.rfind("}")
            if first_brace == -1 or last_brace == -1:
                print("No JSON object found in response")
                return None

            response = response[first_brace:last_brace + 1]
            parsed = json.loads(response)

            required_fields = [
                "Experience Level", "Technical Skills", "Soft Skills",
                "Key Responsibilities", "Tools & Technologies",
                "Education Requirements", "Industry/Domain"
            ]
            for field in required_fields:
                if field not in parsed:
                    print(f"Missing required field: {field}")
                    return None

            return parsed

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Problematic response: {response[:200]}...")
            return None
        except Exception as e:
            print(f"Unexpected error parsing response: {e}")
            return None

    def convert_job_descriptions(self, input_file: str, output_file: str = "cleaned_json.json"):
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"❌ Error: Input file '{input_file}' not found!")
            return None
        except json.JSONDecodeError:
            print(f"❌ Error: Invalid JSON in '{input_file}'!")
            return None

        role = data.get("role", "machine learning engineer")
        descriptions = data.get("descriptions", [])

        if not descriptions:
            print("❌ No job descriptions found in input file!")
            return None

        converted_jobs = []

        print(f"🚀 Processing {len(descriptions)} job descriptions...")
        print("-" * 50)

        for i, description in enumerate(descriptions, 1):
            print(f"📝 Processing job {i}/{len(descriptions)}...")
            ai_response = self.extract_job_fields(description)

            if ai_response:
                parsed_fields = self.parse_json_response(ai_response)
                if parsed_fields:
                    job_entry = {**{"role": role}, **parsed_fields}
                    converted_jobs.append(job_entry)
                    print(f"✅ Successfully processed job {i}")
                else:
                    print(f"❌ Failed to parse AI response for job {i}")
                    with open(f"debug_response_{i}.txt", "w") as debug_file:
                        debug_file.write(ai_response or "No response")
            else:
                print(f"❌ Failed to get AI response for job {i}")
            print("-" * 30)

        if not converted_jobs:
            print("❌ No jobs were successfully converted!")
            return None

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(converted_jobs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error saving output file: {e}")
            return None

        print("=" * 50)
        print("🎉 CONVERSION COMPLETED!")
        print("=" * 50)
        print(f"📁 Output saved to: {output_file}")
        print(f"📊 Successfully processed: {len(converted_jobs)} / {len(descriptions)}")

        return converted_jobs


def main():
    print("🤖 Job Description Converter")
    print("=" * 40)

    try:
        converter = JobDescriptionConverter()
    except ValueError as e:
        print(f"❌ Setup Error: {e}")
        print("\n💡 Please check your .env file and ensure it contains:")
        print("   OPENROUTER_API_KEY=your_api_key")
        return

    input_file = "job_descriptions_machine_learning_engineer.json"
    if not os.path.exists(input_file):
        print(f"❌ Input file '{input_file}' not found!")
        return

    result = converter.convert_job_descriptions(input_file)

    if not result:
        print("\n❌ No jobs were successfully converted. Please check:")
        print("   - API key")
        print("   - Internet connection")
        print("   - Input JSON file format")


if __name__ == "__main__":
    main()
