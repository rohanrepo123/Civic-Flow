from urllib.parse import urlparse

from backend.app.agent.schemas.source import OfficialSource, SourceVerificationStatus


class SourceValidator:
    """Marks sources verified only when their HTTPS host is explicitly allowlisted."""

    def __init__(self, approved_domains: set[str]) -> None:
        self._approved_domains = {domain.casefold().strip(".") for domain in approved_domains}

    def validate(self, source: OfficialSource) -> OfficialSource:
        parsed = urlparse(str(source.source_url))
        host = (parsed.hostname or "").casefold().strip(".")
        domain_approved = any(
            host == domain or host.endswith(f".{domain}")
            for domain in self._approved_domains
        )
        status = (
            SourceVerificationStatus.VERIFIED
            if parsed.scheme == "https" and domain_approved and source.publisher
            else SourceVerificationStatus.UNVERIFIED
        )
        return source.model_copy(update={"verification_status": status})
