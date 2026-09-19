from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    RegisterSerializer,
    UserPublicSerializer,
    VerifySerializer,
)
from apps.identity.services import AuthService


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, _raw_code = AuthService.register(
            email=serializer.validated_data.get("email"),
            phone=serializer.validated_data.get("phone"),
            password=serializer.validated_data["password"],
        )

        return Response(
            {
                "data": {
                    "user_id": str(user.id),
                    "verification_state": user.verification_status,
                }
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService.verify(
            user_id=serializer.validated_data["user_id"],
            code=serializer.validated_data["code"],
        )

        return Response(
            {
                "data": {
                    "verified": True,
                    "user_id": str(user.id),
                    "account_status": user.account_status,
                }
            },
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService.authenticate(
            identifier=serializer.validated_data["identifier"],
            password=serializer.validated_data["password"],
        )
        access_token, refresh_token = AuthService.issue_token_pair(user)

        return Response(
            {
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user": UserPublicSerializer(user).data,
                }
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token, refresh_token = AuthService.rotate_refresh_token(
            serializer.validated_data["refresh_token"]
        )

        return Response(
            {
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.revoke_refresh_token(
            serializer.validated_data["refresh_token"], user=request.user
        )

        return Response({"data": {"success": True}}, status=status.HTTP_200_OK)