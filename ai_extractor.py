import json
import os
from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_missing_contact_fields_with_ai(partner, text_snippet):
    prompt = f"""
Extract only missing public contact fields.

Company:
{partner.get("company_name", "")}

Known email:
{partner.get("contact_email", "")}

Known website:
{partner.get("website", "")}

Known LinkedIn:
{partner.get("linkedin", "")}

Known phone:
{partner.get("phone", "")}

Text snippet:
{text_snippet[:2500]}

Return JSON only:
{{
  "website": "",
  "linkedin": "",
  "phone": "",
  "confidence_score": 0.0,
  "ai_notes": ""
}}

Rules:
- Do not invent values.
- Only return website, LinkedIn, or phone if explicitly present in the text.
- If missing, return an empty string.
- LinkedIn must contain linkedin.com/company or linkedin.com/in.
"""

    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {
                "role": "system",
                "content": "You extract only explicitly present public contact fields from text."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)
