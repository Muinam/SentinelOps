# structured.py
#
# Is file ka kaam: LLM se STRUCTURED (JSON) jawab lena aur usko VALIDATE karna.
# Tareeqa: schema do -> JSON maango -> Pydantic se check karo -> galat ho to
# LLM ko uski ghalti dikha kar dobara maango (repair loop).
# Ye kisi bhi model par chalta hai - provider ke special "JSON mode" par depend nahi.

import json                                           # json - schema ko text me badalne aur jawab parse karne ke liye
import re                                              # re - jawab me se JSON hissa nikalne ke liye
from typing import TypeVar                             # TypeVar - function ko batata hai "jo model do, wahi wapas milega"
from pydantic import BaseModel, ValidationError        # BaseModel - schema base, ValidationError - validation ki ghalti
from app.llm.client import call_llm                    # Hamara LLM wrapper

T = TypeVar("T", bound=BaseModel)                      # T = koi bhi Pydantic model class


class StructuredOutputError(Exception):
    """Raise hota hai jab LLM kai koshishon ke baad bhi valid JSON na de paye."""


def _extract_json(text: str) -> str:
    """
    LLM ke jawab se JSON object nikalta hai - code fences (```json ... ```) ya
    aage peeche ke extra alfaaz hataa kar.
    """
    cleaned = re.sub(r"```(?:json)?", "", text)         # ```json aur ``` wale markers hata do
    start = cleaned.find("{")                            # Pehla "{" kahan hai
    end = cleaned.rfind("}")                              # Aakhri "}" kahan hai
    if start == -1 or end == -1 or end < start:           # Agar JSON object mila hi nahi
        raise ValueError("jawab me koi JSON object nahi mila")
    return cleaned[start:end + 1]                          # Sirf { ... } wala hissa wapas karo


def call_llm_json(messages: list, model_cls: type[T], max_attempts: int = 3, max_tokens: int = 2048) -> T:
    """
    LLM se model_cls ke shape ka JSON maangta hai, validate karta hai, aur
    galat hone par max_attempts tak repair karta hai.

    Return: model_cls ka valid object. Fail hone par StructuredOutputError.
    """
    schema_text = json.dumps(model_cls.model_json_schema(), separators=(",", ":"))  # Schema compact text me
    instruction = (                                         # LLM ko batao kaisa jawab chahiye
        "\n\nRespond with ONLY one JSON object that matches this JSON Schema. "
        "No explanations, no markdown, no code fences.\nSchema:\n" + schema_text
    )

    working = [dict(m) for m in messages]                   # Messages ki copy - asal list ko na chhedein
    working[-1]["content"] = working[-1]["content"] + instruction  # Aakhri (user) message me schema jod do

    last_error = "unknown error"                             # Aakhri ghalti yaad rakhne ke liye
    for attempt in range(1, max_attempts + 1):               # Zyada se zyada max_attempts koshishen
        response = call_llm(messages=working, max_tokens=max_tokens)   # LLM ko call karo
        text = response.choices[0].message.content or ""     # Jawab ka text (None ho to khali string)
        try:
            raw_json = _extract_json(text)                    # Text se JSON hissa nikalo
            return model_cls.model_validate_json(raw_json)    # Pydantic se parse + validate - sahi hai to yahin return
        except (ValidationError, ValueError) as error:        # JSON toota hua ya schema se mel nahi khata
            last_error = str(error)[:600]                      # Ghalti ka chhota text (lambi na ho)
            print(f"[LLM-JSON] {model_cls.__name__} attempt {attempt} invalid: {last_error[:120]}")  # Debug ke liye
            working.append({"role": "assistant", "content": text})   # LLM ka galat jawab history me daalo
            working.append({                                          # Phir usko ghalti dikha kar dobara maango
                "role": "user",
                "content": f"Your JSON was invalid: {last_error}\nReturn ONLY the corrected JSON object.",
            })

    raise StructuredOutputError(f"{model_cls.__name__}: {max_attempts} koshishon ke baad bhi valid JSON nahi mila ({last_error})")
