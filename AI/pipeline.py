import os
import re
from typing import List, Dict, Tuple

from huggingface_hub import InferenceClient
from transformers import pipeline
from datasets import load_dataset


class MindPal_Pipeline:
    def __init__(self):

        hf_token = os.environ.get("HUGGING_FACE_TOKEN")
        if not hf_token:
            raise RuntimeError(
                "Missing HUGGING_FACE_TOKEN in environment variables. "
                "Please export HUGGING_FACE_TOKEN before running the API."
            )


        self.model_id = "deepseek-ai/DeepSeek-R1"


        self.client = InferenceClient(token=os.environ.get("HUGGING_FACE_TOKEN"))


        self.emotion_classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=1
        )


        self.SLANG_MAP = self.load_slang_dataset() or {}

 
    def normalize_text(self, text: str) -> str:
        t = text.strip()
        t = re.sub(r"\s+", " ", t)
        return t

    def load_slang_dataset(self) -> Dict[str, List[str]]:
        try:
            ds = load_dataset("MLBtrio/genz-slang-dataset", split="train")
            slang_map = {}
            for row in ds:
                key = row.get("Slang")
                desc = row.get("Description")
                if key:
                    slang_map[key.lower()] = [desc] if desc else []
            return slang_map if slang_map else None
        except Exception as e:
            print(f"[WARN] Failed to load GenZ slang dataset: {e}")
            return None

    def detect_slang_candidates(self, text: str) -> List[Tuple[str, List[str]]]:
        lower = text.lower()
        found = []
        for s in self.SLANG_MAP:
            if re.search(r"\b" + re.escape(s) + r"\b", lower):
                found.append((s, self.SLANG_MAP[s]))
        return found

    def map_slang_in_text(self, text: str) -> str:
        context = text
        candidates = self.detect_slang_candidates(text)
        if not candidates:
            return context

        slang_token, meanings = candidates[0]
        meaning_text = meanings[0] if meanings else ""
        repl = f"{slang_token} ({meaning_text})" if meaning_text else slang_token

        return re.sub(
            r"\b" + re.escape(slang_token) + r"\b",
            repl,
            context,
            flags=re.IGNORECASE
        )

 
    def emotion_detection(self, text: str) -> str:
        pred = self.emotion_classifier(text)
        if isinstance(pred, list) and len(pred) > 0:
 
            first = pred[0]
            if isinstance(first, list) and first:
                return first[0]["label"]
            return first.get("label", "unknown")
        return "unknown"


    def generate_response(self, text: str, detected_emotion: str) -> str:
        system_prompt = f"""
You are MindPal, a supportive wellbeing chatbot for 13-15 year-old Australian teens.
Your responses should be:
- Warm, understanding, and age-appropriate
- Validate their feelings without being condescending
- Use language that feels natural to teens
- Acknowledge and reflect their feeling(s)
- Keep replies within 1-3 sentences and sound like a natural conversation
- Encourage them to talk more, ask follow up questions
- Encourage real-life support systems and resources
- When appropriate, gently encourage the teen to talk with a trusted adult or friend
- Avoid shaming or lecturing
- Use emojis to express emotions
- Do NOT give medical or clinical advice
- Do NOT let the user give out personal information
- If user asks unrelated questions, politely decline and redirect the conversation back

Current emotion detected: {detected_emotion}

Always rethink and double check your answer before responding.
""".strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]


        try:
            completion = self.client.chat_completion(
                model="mistralai/Mistral-7B-Instruct-v0.3",
                messages=messages,
                max_tokens=256,
                temperature=0.3,
                top_p=0.9,

            )
            raw_reply = completion.choices[0].message["content"]
        except AttributeError:

            completion = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_tokens=256,
                temperature=0.3,
                top_p=0.9,
            )

            raw_reply = completion.choices[0].message.content

        reply = (raw_reply or "").strip()
        if "</think>" in reply:
            reply = reply.split("</think>")[-1].strip()


        return reply

    def chat(self, text: str) -> str:
        text = self.normalize_text(text)
        text = self.map_slang_in_text(text)
        detected_emotion = self.emotion_detection(text)
        reply = self.generate_response(text, detected_emotion)
        return reply
