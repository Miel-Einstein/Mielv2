from django.urls import path

from events.consumers import EventConsumer

websocket_urlpatterns = [path("ws/e/<slug:slug>/", EventConsumer.as_asgi())]
