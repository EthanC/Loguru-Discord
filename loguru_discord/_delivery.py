"""Share context-local webhook delivery state with logging interception."""

from contextvars import ContextVar

delivery_active: ContextVar[bool] = ContextVar("webhook_delivery_active", default=False)
