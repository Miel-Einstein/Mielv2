"""WebSocket d'un événement : tous les écrans ouverts reçoivent les mêmes messages
(moment fort lancé, nouveau vœu, réaction, arrivée). Lecture seule côté client."""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from events.models import Event


class EventConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        slug = self.scope["url_route"]["kwargs"]["slug"]
        event_id = await database_sync_to_async(lambda: Event.objects.filter(slug=slug).values_list("id", flat=True).first())()
        if not event_id:
            await self.close()
            return
        self.group = f"event-{event_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def event_message(self, message):
        await self.send_json({"kind": message["kind"], "payload": message["payload"], "server_now": message["server_now"]})
