# schemas.py
#
# Is file ka kaam: LLM ke har STRUCTURED jawab ka SHAPE define karna (Pydantic models).
# Pehle hum text me "ROOT_CAUSE:" dhoondte the (fragile). Ab LLM se JSON maangte hain
# aur Pydantic usko VALIDATE karta hai - galat shape/value aaye to error pakda jata hai.

from typing import Literal                          # Literal - "sirf in values me se ek" ka type
from pydantic import BaseModel, Field, field_validator  # BaseModel - schema ki base class, Field - limits, field_validator - custom check


class Diagnosis(BaseModel):
    """Diagnosis node ka structured jawab."""

    fault_found: bool                                           # Kya evidence me asal fault dikhta hai? (user ka dawa sach hona zaroori nahi)
    root_cause: str = Field(min_length=10, max_length=500)       # Asal wajah, kam az kam 10 aur zyada se zyada 500 characters
    severity: Literal["Low", "Medium", "High", "Critical"]       # Sirf ye 4 values allowed hain
    evidence: list[str] = Field(min_length=1, max_length=6)      # 1 se 6 CHHOTE quotes jo status/logs se hu-ba-hu copy hue hon
    confidence: float = Field(ge=0.0, le=1.0)                    # Bharosa 0.0 se 1.0 ke beech

    @field_validator("severity", mode="before")                  # "before" - Literal check se PEHLE ye chalega
    @classmethod
    def _normalize_severity(cls, value):
        """'high', 'HIGH ' jaisi values ko 'High' bana deta hai (LLM ki chhoti spelling ghaltiyan maaf)."""
        if isinstance(value, str):                                # Sirf string par kaam karo
            return value.strip().capitalize()                       # Spaces hatao aur pehla harf bada karo
        return value                                                 # Baaki types ko waise hi chhod do (Literal reject karega)


class SolutionPlan(BaseModel):
    """Solution node ka structured jawab - ab action CHUNA jata hai, sirf text nahi."""

    action: Literal["restart_container", "manual_intervention"]  # Hamare paas sirf ek automated action hai: restart
    explanation: str = Field(min_length=10, max_length=800)      # Kyun ye action (ya insaan kya kare)

    @field_validator("action", mode="before")
    @classmethod
    def _normalize_action(cls, value):
        """'Restart_Container ' jaisi values ko lowercase/trim kar deta hai."""
        if isinstance(value, str):
            return value.strip().lower()                            # Lowercase kar ke match karwao
        return value


class Critique(BaseModel):
    """Critic node ka structured jawab - diagnosis ko check karne wale judge ka faisla."""

    supported: bool                                              # Kya diagnosis evidence se SABIT hota hai?
    issues: list[str] = Field(default_factory=list, max_length=6)  # Masle (khali bhi ho sakti hai)
    feedback: str = Field(min_length=3, max_length=500)           # Diagnosis agent ke liye hidayat
