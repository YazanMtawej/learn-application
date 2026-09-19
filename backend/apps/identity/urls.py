from django.urls import path

from apps.identity import views

app_name = "identity"

urlpatterns = [
    path("register", views.RegisterView.as_view(), name="register"),
    path("verify", views.VerifyView.as_view(), name="verify"),
    path("login", views.LoginView.as_view(), name="login"),
    path("refresh", views.RefreshView.as_view(), name="refresh"),
    path("logout", views.LogoutView.as_view(), name="logout"),
]