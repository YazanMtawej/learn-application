from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.subscriptions.models import Plan
from apps.subscriptions.serializers import PlanSerializer, UpgradeRequestSerializer
from apps.subscriptions.services import SubscriptionService
from apps.subscriptions.webhook_security import verify_webhook_signature


class PlansListView(APIView):
    """CONFIRMED — Phase 7 §4.9 SUB-PLANS."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = Plan.objects.all().order_by("code")
        return Response({"data": {"plans": PlanSerializer(plans, many=True).data}})


class SubscriptionStateView(APIView):
    """CONFIRMED — Phase 7 §4.9 SUB-STATE."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        current = SubscriptionService.get_current_subscription(request.user)

        if current is None:
            return Response(
                {
                    "data": {
                        "status": "free",
                        "plan": Plan.Code.FREE,
                        "grace_period_end": None,
                    }
                }
            )

        return Response(
            {
                "data": {
                    "status": current.status,
                    "plan": current.plan.code,
                    "grace_period_end": current.grace_period_end,
                }
            }
        )


class SubscriptionUpgradeView(APIView):
    """CONFIRMED — Phase 7 §4.9 SUB-UPGRADE."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpgradeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription = SubscriptionService.upgrade(
            user=request.user,
            plan_id=serializer.validated_data["plan_id"],
            payment_method_ref=serializer.validated_data["payment_method_ref"],
        )

        return Response(
            {"data": {"subscription_status": subscription.status}},
            status=status.HTTP_200_OK,
        )


class SubscriptionCancelView(APIView):
    """CONFIRMED — Phase 7 §4.9 SUB-CANCEL."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = SubscriptionService.cancel(request.user)
        return Response(
            {"data": {"effective_end_date": subscription.current_period_end}},
            status=status.HTTP_200_OK,
        )


class PaymentWebhookView(APIView):
    """
    CONFIRMED endpoint concept — Phase 7 §4.9 SUB-WEBHOOK.
    Auth: Webhook Signature (not JWT) — Phase 7 §4.9/§12.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        verify_webhook_signature(request)
        SubscriptionService.process_webhook(request.data)
        return Response({"data": {"ack": True}}, status=status.HTTP_200_OK)