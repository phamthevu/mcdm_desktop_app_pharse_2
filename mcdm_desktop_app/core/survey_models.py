from dataclasses import dataclass, asdict
from typing import Any, Dict, List

@dataclass
class SurveyQuestion:
    question_id: str
    question_text: str
    question_type: str
    required: bool = False
    options: str = ""
    min_value: Any = None
    max_value: Any = None
    default_value: str = ""
    validation: str = ""
    description: str = ""
    display_order: int = 0

    def to_dict(self): return asdict(self)

SUPPORTED_TYPES = [
    "TITLE", "SECTION", "DESCRIPTION", "SHORT_TEXT", "LONG_TEXT",
    "SINGLE_CHOICE", "MULTIPLE_CHOICE", "DROPDOWN", "INTEGER", "DECIMAL",
    "LIKERT", "RATING", "SLIDER", "DATE", "TIME", "DATETIME", "YES_NO",
    "BOOLEAN", "EMAIL", "PHONE"
]

def survey_config_to_dict(questions: List[SurveyQuestion], auth_mode="Account") -> Dict[str, Any]:
    return {"survey_schema_version": 1, "auth_mode": auth_mode, "questions": [q.to_dict() for q in questions]}
