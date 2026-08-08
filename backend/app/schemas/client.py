from app.schemas._base import StrictModel


class ClientVersionOut(StrictModel):
    # Semver strings, e.g. "1.4.0". min_supported == "0.0.0" means the gate is
    # off and every client version is accepted.
    min_supported: str
    latest: str
