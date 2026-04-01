from src.services.email.base import BaseEmailProvider

PROVIDERS: dict[str, type[BaseEmailProvider]] = {}


def _register_providers():
    from src.services.email.smtp import SMTPEmailProvider
    from src.services.email.sendgrid import SendGridEmailProvider
    from src.services.email.mailgun import MailgunEmailProvider

    PROVIDERS["smtp"] = SMTPEmailProvider
    PROVIDERS["sendgrid"] = SendGridEmailProvider
    PROVIDERS["mailgun"] = MailgunEmailProvider


def get_email_provider(provider_type: str, config: dict) -> BaseEmailProvider:
    if not PROVIDERS:
        _register_providers()
    cls = PROVIDERS.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown email provider: {provider_type}")
    return cls(**config)


def get_all_provider_schemas() -> dict[str, list[dict]]:
    if not PROVIDERS:
        _register_providers()
    return {name: cls.config_schema() for name, cls in PROVIDERS.items()}
