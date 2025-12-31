# queues/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slug = self.scope['url_route']['kwargs']['slug']
        self.room_group_name = f'queue_{self.slug}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from room group (Dari Views.py)
    async def queue_update(self, event):
        message = event['message']
        data = event['data']

        # Send message to WebSocket (Ke HTML/JS)
        await self.send(text_data=json.dumps({
            'message': message,
            'data': data
        }))