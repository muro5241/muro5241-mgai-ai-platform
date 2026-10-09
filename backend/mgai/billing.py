"""Contract for a future payment adapter. No checkout/webhook is enabled today."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VerifiedBillingEvent:
    """Only construct after validating the provider's original signed request bytes."""

    provider_event_id: str
    customer_id: str
    subscription_id: str
    state: str


class BillingProvider(Protocol):
    async def checkout_url(self, user_id: str, server_plan_id: str) -> str: ...
    def verify_webhook(
        self, raw_body: bytes, signature: str
    ) -> VerifiedBillingEvent: ...


# A production adapter must verify timestamp/signature, bind customer to user on
# the server, load prices from reviewed plan IDs, reconcile with the provider and
# claim BillingEvent.provider_event_id exactly once in the credit transaction.
# Browser "payment success" redirects must never grant credits or subscriptions.
