"""Messenger dispatcher: выбрать sender + шаблон/текст + залогировать touch."""
import os
from loguru import logger

from granite.messenger.base import SendResult
from granite.messenger.tg_sender import TgSender
from granite.messenger.wa_sender import WaSender
from granite.api.stage_transitions import apply_outgoing_touch
from granite.templates import EmailTemplate
from granite.database import CrmTouchRow, CrmContactRow


class MessengerDispatcher:
    """Отправка сообщений через мессенджеры с logging в CRM."""

    def __init__(self):
        self.tg = TgSender()
        self.wa = WaSender()
        from granite.constants import get_sender_field
        self.from_name = get_sender_field("from_name")
        self.whatsapp_number = get_sender_field("whatsapp")
        self.telegram_link = get_sender_field("telegram")

    def send(
        self,
        channel: str,
        contact_id: str,
        template: EmailTemplate | None = None,
        text: str = "",
        company_name: str = "",
        city: str = "",
        db_session=None,
        company_id: int | None = None,
    ) -> SendResult:
        """Отправить сообщение через мессенджер.

        Args:
            channel: "tg" или "wa"
            contact_id: username TG или номер телефона WA
            template: EmailTemplate (из TemplateRegistry, если text не передан — рендерит из шаблона)
            text: готовый текст сообщения (приоритетнее template)
            company_name: название компании (для плейсхолдеров)
            city: город (для плейсхолдеров)
            db_session: SQLAlchemy session. Если передана — логирует touch.
            company_id: ID компании для touch.

        Returns:
            SendResult
        """
        sender = {"tg": self.tg, "wa": self.wa}.get(channel)
        if not sender:
            return SendResult(
                success=False, channel=channel, contact_id=contact_id,
                error=f"Unknown channel: {channel}",
            )

        # Определяем текст: прямой приоритетнее шаблона
        if text:
            message = text
        elif template:
            from granite.city_declensions import get_locative
            render_kwargs = {
                "from_name": self.from_name,
                "whatsapp_number": self.whatsapp_number,
                "telegram_link": self.telegram_link,
                "city": city,
                "city_locative": get_locative(city),
                "company_name": company_name,
            }
            message = template.render(**render_kwargs)
        else:
            return SendResult(
                success=False, channel=channel, contact_id=contact_id,
                error="No text or template provided",
            )

        # Отправка
        result = sender.send(contact_id, message)

        # Логирование в CRM (если передана сессия)
        if db_session is not None and company_id is not None and result.success:
            touch = CrmTouchRow(
                company_id=company_id,
                channel=channel,
                direction="outgoing",
                body=message,
                note=f"[{channel.upper()} mock sent to {result.contact_id}]",
            )
            db_session.add(touch)

            contact = db_session.get(CrmContactRow, company_id)
            if contact:
                apply_outgoing_touch(contact, channel)

        return result
