"""
Mastery state enum and transition ordering.

CONFIRMED — Phase 15 §9: exactly 5 states, no others. The linear
STATE_ORDER below encodes the total order implied by Phase 15 §10's
transition diagram (Not Assessed → Insufficient Evidence → Developing
→ Proficient → Mastered), used only to compare "how many steps apart"
two states are for the transition-guard rules in services.py — it is
not itself an invented business rule, only a data structure expressing
the documented linear progression.
"""

NOT_ASSESSED = "not_assessed"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
DEVELOPING = "developing"
PROFICIENT = "proficient"
MASTERED = "mastered"

STATE_ORDER = [
    NOT_ASSESSED,
    INSUFFICIENT_EVIDENCE,
    DEVELOPING,
    PROFICIENT,
    MASTERED,
]

STATE_CHOICES = [(s, s) for s in STATE_ORDER]