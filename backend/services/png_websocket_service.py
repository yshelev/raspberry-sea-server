from services.websocket_service_base import WebsocketServiceBase
import base64

class PNGWebsocketService(WebsocketServiceBase): 
    def __init__(self):
        super().__init__()
    
    async def send_data(self, data: dict) -> tuple[bool, str]: 
        """
        Отправка png картинки, путь до картинки должен находится в data по ключу "image_path"
        
        :param self: Description
        :param data: Description
        :type data: dict
        """
        
        image_path = data.get("image_path")
        if not image_path: 
            return False, "image path not found"
    
        try: 
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
        except FileNotFoundError: 
            return False, "image path not found"
        except Exception as e: 
            return False, f"unknown error, {e}"

        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        payload = {
            "type": "polar_image",
            "data": image_base64,
        }
        
        try: 
            await self._send_payload_data(payload)
        except Exception as e: 
            return False, f"unknown error, {e}"
        
        return True, None