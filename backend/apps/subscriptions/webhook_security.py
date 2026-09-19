import hashlib
import hmac

from django.conf import settings

from apps.subscriptions.exceptions import InvalidWebhookSignatureError

SIGNATURE_HEADER = "HTTP_X_WEBHOOK_SIGNATURE"


def verify_webhook_signature(request) -> None:
    """
    Phase 7 §12: "SUB-WEBHOOK يتحقق من توقيع المزوّد (Signature) بدل JWT —
    مصدر ثقة مختلف تمامًا عن باقي الـAPI". No specific payment provider is
    chosen anywhere in Phase 0-17, so this implements a generic
    HMAC-SHA256 signature check over the raw request body against a
    configured shared secret, rather than integrating a specific vendor
    SDK (which is explicitly out of scope — Phase 1 §1.2: payment gateway
    integration detail is Phase 24).
    """
    provided_signature = request.META.get(SIGNATURE_HEADER)
    if not provided_signature:
        raise InvalidWebhookSignatureError()

    expected_signature = hmac.new(
        settings.PAYMENT_WEBHOOK_SECRET.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_signature, expected_signature):
        raise InvalidWebhookSignatureError()