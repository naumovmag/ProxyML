from src.services.verification.base import BaseVerificationProvider

CHANNEL_PROVIDERS: dict[str, dict[str, type[BaseVerificationProvider]]] = {}

CHANNEL_META = {
    "email": {"label": "Email", "icon": "mail", "description": "Send verification links or codes via email"},
    "sms": {"label": "SMS", "icon": "smartphone", "description": "Send verification codes via SMS"},
    "telegram": {"label": "Telegram", "icon": "send", "description": "Send verification codes via Telegram bot"},
}

PROVIDER_LABELS = {
    "smtp": "SMTP",
    "sendgrid": "SendGrid",
    "mailgun": "Mailgun",
    "twilio": "Twilio",
    "sms_ru": "SMS.ru",
    "telegram_bot": "Telegram Bot",
}


def _register_providers():
    from src.services.verification.email.smtp import SmtpVerificationProvider
    from src.services.verification.email.sendgrid import SendgridVerificationProvider
    from src.services.verification.email.mailgun import MailgunVerificationProvider
    from src.services.verification.sms.twilio import TwilioSmsProvider
    from src.services.verification.sms.sms_ru import SmsRuProvider
    from src.services.verification.telegram.bot import TelegramBotProvider

    CHANNEL_PROVIDERS["email"] = {
        "smtp": SmtpVerificationProvider,
        "sendgrid": SendgridVerificationProvider,
        "mailgun": MailgunVerificationProvider,
    }
    CHANNEL_PROVIDERS["sms"] = {
        "twilio": TwilioSmsProvider,
        "sms_ru": SmsRuProvider,
    }
    CHANNEL_PROVIDERS["telegram"] = {
        "telegram_bot": TelegramBotProvider,
    }


def _ensure_registered():
    if not CHANNEL_PROVIDERS:
        _register_providers()


def get_verification_provider(channel_type: str, provider_type: str, config: dict) -> BaseVerificationProvider:
    _ensure_registered()
    providers = CHANNEL_PROVIDERS.get(channel_type)
    if not providers:
        raise ValueError(f"Unknown channel type: {channel_type}")
    cls = providers.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown provider '{provider_type}' for channel '{channel_type}'")
    return cls(**config)


def get_all_channel_schemas() -> dict:
    _ensure_registered()
    result = {}
    for ch_type, providers in CHANNEL_PROVIDERS.items():
        meta = CHANNEL_META.get(ch_type, {})
        provider_schemas = {}
        for prov_type, prov_cls in providers.items():
            provider_schemas[prov_type] = {
                "label": PROVIDER_LABELS.get(prov_type, prov_type),
                "config_schema": prov_cls.config_schema(),
            }
        result[ch_type] = {
            "label": meta.get("label", ch_type),
            "icon": meta.get("icon", ""),
            "description": meta.get("description", ""),
            "providers": provider_schemas,
        }
    return result


def get_channel_types() -> list[dict]:
    _ensure_registered()
    return [
        {"type": ch_type, **CHANNEL_META.get(ch_type, {"label": ch_type, "icon": "", "description": ""})}
        for ch_type in CHANNEL_PROVIDERS
    ]
