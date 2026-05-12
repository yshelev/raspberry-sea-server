from services.websocket_service_base import WebsocketServiceBase

class DataWebsocketService(WebsocketServiceBase): 
    def __init__(self):
        super().__init__()
        
    async def send_data(self, data) -> tuple[bool, str]: 
        try: 
            await self._send_payload_data(data)
        except Exception as e: 
            return False, f"unknown error: {e}"

        return True, None