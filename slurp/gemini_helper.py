from google import genai
import json

from google.genai import types


class GeminiHelper:
    def __init__(self, api_key: str):
        self.genai_client = genai.Client(api_key=api_key)
        self.stats_total_token_count_stream = []
        self.avg_token_util = 0
        self.model = 'gemini-2.0-flash-001'
        self.cache = None

    def set_cached_content(self, cache_name, content, ttl="300s"):
        self.cache = self.genai_client.caches.create(
            model=self.model,
            config=types.CreateCachedContentConfig(
                display_name=cache_name,  # used to identify the cache
                system_instruction=content,
                ttl=ttl,
            )
        )

    def generate_content(self, prompt: str) -> dict:
        try:
            response_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "title": "Code Interaction Q&A",
                "description": "Schema for capturing the status and response to code exploration.",
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "The status of the response generation."
                    },
                    "answer": {
                        "type": "string",
                        "description": "The answer or response to the user question."
                    }
                },
                "required": [
                    "status",
                    "answer"
                ],
                "additionalProperties": False
            }
            response = self.genai_client.models.generate_content(model=self.model,
                                                                 contents=types.Content(role="user", parts=[
                                                                     types.Part.from_text(text=prompt)]),
                                                                 config=types.GenerateContentConfig(temperature=0.1,
                                                                                                    max_output_tokens=30000,
                                                                                                    response_json_schema=response_schema,
                                                                                                    cached_content=self.cache.name,
                                                                                                    response_mime_type="application/json"))
            if len(self.stats_total_token_count_stream) == 10:
                s = 0
                for v in self.stats_total_token_count_stream:
                    s += v
                self.avg_token_util = s / 10
            self.stats_total_token_count_stream.append(response.usage_metadata.total_token_count)
            # get first response
            selected_response = response.candidates[0] if len(response.candidates) > 0 else None
            if selected_response:
                text = selected_response.content.parts[0].text
                return json.loads(text)
            else:
                print("Candidate answer not found")
                return {}
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return {}  # Return empty or handle error gracefully
