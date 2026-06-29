from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class AppState:
    current_model_name: str = "None"
    last_assistant_response: str = ""
    current_session: str = "default"
    run_globals: Dict[str, Any] = field(default_factory=dict)

state = AppState()
