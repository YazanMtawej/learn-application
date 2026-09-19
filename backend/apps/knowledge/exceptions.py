class AppendOnlyViolationError(Exception):
    """
    Application-layer enforcement of Phase 8 §4.5's Evidence invariant:
    "لا UPDATE/DELETE على مستوى التطبيق". Phase 8 itself marks the
    DB-trigger-level enforcement as "TBD تنفيذيًا" — this is the
    documented Application Layer enforcement it explicitly calls for.
    """