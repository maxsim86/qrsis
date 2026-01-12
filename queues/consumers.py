# queues/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['slug']
        self.room_group_name = f'queue_{self.room_name}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Handler mesej dari views.py
    async def queue_update(self, event):
        # PENTING: Hantar JSON, BUKAN HTML
        await self.send(text_data=json.dumps({
            'message': event['message'], # contoh: 'invite_next'
            'data': event['data']        # data tiket
        }))