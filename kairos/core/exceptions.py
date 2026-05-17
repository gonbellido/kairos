class KairosError(Exception):
    pass


class ProfileNotFoundError(KairosError):
    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        super().__init__(f"Profile not found: {profile_id}")


class CaseNotFoundError(KairosError):
    def __init__(self, case_id: str):
        self.case_id = case_id
        super().__init__(f"Case not found: {case_id}")


class ImprontaValidationError(KairosError):
    def __init__(self, msg: str):
        super().__init__(f"Impronta validation error: {msg}")


class PluginLoadError(KairosError):
    def __init__(self, name: str, reason: str):
        super().__init__(f"Failed to load plugin '{name}': {reason}")


class ScoringError(KairosError):
    def __init__(self, msg: str):
        super().__init__(f"Scoring error: {msg}")
