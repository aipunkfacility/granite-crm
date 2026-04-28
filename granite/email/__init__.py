"""Email-модули Granite CRM.

FIX-A4: Удобные реэкспорты для импорта одной строкой:
    from granite.email import determine_ab_variant, validate_recipients
    from granite.email import maybe_create_followup_task, increment_campaign_opened
"""
from granite.email.ab import determine_ab_variant
from granite.email.validator import validate_recipients, check_gmail_block_signs
from granite.email.followup_logic import maybe_create_followup_task, increment_campaign_opened

__all__ = [
    "determine_ab_variant",
    "validate_recipients",
    "check_gmail_block_signs",
    "maybe_create_followup_task",
    "increment_campaign_opened",
]
