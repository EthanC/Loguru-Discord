"""Share configuration and payload construction between webhook sinks."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from clyde import Markdown, RequestPolicy, Timestamp, Webhook
from clyde.components import Container, Seperator, SeperatorSpacing, TextDisplay
from clyde.webhook import MessageFlags
from msgspec import UNSET, UnsetType


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """Retain formatted text and level information without a Loguru record."""

    text: str
    level_name: str
    level_no: int
    timestamp: datetime


class PayloadConfig:
    """Configure a webhook template without network or file operations."""

    def __init__(
        self,
        webhook_url: str,
        *,
        thread_id: str | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
        avatar: UnsetType | None | str | bytes | Path = UNSET,
        rich: bool = False,
        critical_color: str | int | None = "000000",
        error_color: str | int | None = "D22D39",
        warning_color: str | int | None = "CE9C5C",
        success_color: str | int | None = "43A25A",
        info_color: str | int | None = "FFFFFF",
        debug_color: str | int | None = "5865F2",
        trace_color: str | int | None = None,
        intercept: bool = False,
        intercept_level_map: dict[str, str] | None = None,
        suppress: list[type[BaseException]] | None = None,
        request_policy: RequestPolicy | None = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.thread_id = thread_id
        self.username = username
        self.avatar_url = avatar_url
        self.avatar = avatar
        self.rich = rich
        self.critical_color = critical_color
        self.error_color = error_color
        self.warning_color = warning_color
        self.success_color = success_color
        self.info_color = info_color
        self.debug_color = debug_color
        self.trace_color = trace_color
        self.intercept = intercept
        self.intercept_level_map = intercept_level_map
        self.suppress = suppress
        if request_policy is not None and not isinstance(request_policy, RequestPolicy):
            raise TypeError("request_policy must be a Clyde RequestPolicy or None")
        self.request_policy = request_policy or RequestPolicy(
            connect_timeout=5.0,
            read_timeout=10.0,
            max_rate_limit_retries=3,
            total_timeout=30.0,
        )
        self.webhook = Webhook(url=webhook_url)
        if thread_id is not None:
            self.webhook.set_thread_id(thread_id)
        if username:
            self.webhook.set_username(username)
        if avatar_url:
            self.webhook.set_avatar_url(avatar_url)

    def _suppressed(self, exception: BaseException | None) -> bool:
        """Check exception suppression before retaining a delivery record."""
        return bool(self.suppress and isinstance(exception, tuple(self.suppress)))

    def _payload(self, record: DeliveryRecord) -> Webhook:
        """Build an isolated payload, falling back to a UTF-8 text attachment."""
        webhook = deepcopy(self.webhook)
        body = Markdown.code_block(record.text)
        if self.rich:
            heading = Markdown.header_3(record.level_name)
            footer = Markdown.subtext(
                f"{Timestamp.long_date_time(record.timestamp)} ({Timestamp.relative_time(record.timestamp)})"
            )
            if len(heading) + len(body) + len(footer) <= 4000:
                container = Container(
                    components=[
                        TextDisplay(content=heading),
                        TextDisplay(content=body),
                        Seperator(divider=True, spacing=SeperatorSpacing.SMALL),
                        TextDisplay(content=footer),
                    ]
                )
                color = {
                    50: self.critical_color,
                    40: self.error_color,
                    30: self.warning_color,
                    25: self.success_color,
                    20: self.info_color,
                    10: self.debug_color,
                    5: self.trace_color,
                }.get(record.level_no)
                if color is not None:
                    container.set_accent_color(color)
                webhook.add_component(container)
            else:
                webhook.components = UNSET
                webhook.set_flag(MessageFlags.IS_COMPONENTS_V2, None)
                webhook._remove_query_param("with_components")
                webhook.add_attachment("message.txt", record.text.encode())
        elif len(body) > 2000:
            webhook.add_attachment("message.txt", record.text.encode())
        else:
            webhook.set_content(body)
        return webhook
