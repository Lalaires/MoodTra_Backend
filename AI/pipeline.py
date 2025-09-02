import os
import re
import string
import contractions
from typing import List, Dict, Tuple

from huggingface_hub import InferenceClient
from transformers import pipeline
from datasets import load_dataset
from google import genai


class MindPal_Pipeline:
    def __init__(self):

        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            raise RuntimeError(
                "Missing GOOGLE_API_KEY in environment variables."
            )

        self.model = "gemini-2.5-pro"

        self.client = genai.Client(api_key=GOOGLE_API_KEY)

        self.emotion_classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=None
        )

        self.SLANG_MAP = self.load_slang_dataset()


    def normalize_text(self, text: str) -> str:
        t = " ".join(text.split()).strip()
        t = t.lower()
        t = t.translate(str.maketrans('', '', string.punctuation))
        t = contractions.fix(t)
        return t

    def load_slang_dataset(self) -> Dict[str, List[str]]:
        try:
            ds = load_dataset("MLBtrio/genz-slang-dataset", split="train")
            slang_map = {}
            for row in ds:
                key = row.get("Slang")
                desc = row.get("Description")
                if key:
                    slang_map[key.lower()] = desc
            return slang_map if slang_map else None
        except Exception as e:
            print(f"[WARN] Failed to load GenZ slang dataset: {e}")
            return None

    def detect_and_map_slang(self, text: str) -> str:
        for s in self.SLANG_MAP:
            if re.search(r"\b" + re.escape(s) + r"\b", text.lower()):
                slang_token, meaning = s, self.SLANG_MAP[s]
                replace = f"{slang_token} ({meaning})"
                text = re.sub(r"\b" + re.escape(slang_token) + r"\b", replace, text, flags=re.IGNORECASE)
        return text

    def emotion_detection(self, text: str) -> str:
        emotion = self.emotion_classifier(text)
        return emotion[0]

    def generate_response(self, text: str, detected_emotion: str) -> str:
        prompt = f"""
        You are MindPal, a supportive wellbeing chatbot for 13-15 year-old Australian teens.
        Your responses should be:
        - Warm, understanding, and age-appropriate
        - Validate their feelings without being condescending
        - Use language that feels natural to teens
        - Acknowledge and reflect their feeling(s)
        - Keep replies within 1-3 sentences and sound like a natural conversation
        - Encourage them to talk more, ask follow up questions and let user express their feelings
        - Encourage real-life support systems and resources
        - When appropriate, gently encourage the teen to talk with a trusted adult or friend
        - Avoid shaming or lecturing
        - Use emojis to express emotions
        - Do NOT encourage any dangerous behaviour or provide inappropriate information
        - Do NOT give medical or clinical advice or replace professional help
        - Do NOT be overly positive or negative, be neutral and honest when necessary
        - Do NOT let the user give out any personal information
        - If user asks questions that are unrelated to your purpose, politely decline to answer and redirect the conversation back

        Current emotion(s) detected: {detected_emotion}
        user's message: {text}

        Always rethink and double check your answer before responding.
        When you completely understand you can start the session.
        """

        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
        except Exception as e:
            print(f"[WARN] Failed to generate response: {e}")
            return None

        return response.text

    def chat(self, text: str) -> str:
        text = self.normalize_text(text)
        text = self.detect_and_map_slang(text)
        detected_emotion = self.emotion_detection(text)
        reply = self.generate_response(text, detected_emotion)
        return reply
