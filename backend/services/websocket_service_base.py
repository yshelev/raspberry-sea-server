import json 
import logging
from fastapi import WebSocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsocketServiceBase: 
    def __init__(self):
        self.clients: list[WebSocket] = []
        
    def add_to_clients(self, websocket_connection): 
        self.clients.append(websocket_connection)
    
    def remove_client(self, websocket_connection): 
        if websocket_connection in self.clients: 
            self.clients.remove(websocket_connection)
    
    async def send_data(self, data: dict) -> tuple[bool, str]: 
        raise NotImplementedError()    
    
    async def _send_payload_data(self, payload: dict): 
        for ws in self.clients[:]:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception as e:
                logger.error(f"Error sending PNG to client: {e}")
                if ws in self.clients:
                    self.clients.remove(ws)
                
                raise Exception(e)