"""RapidAPI Image Caption Generator vision operation."""

import os
import base64
from typing import Dict, Any, AsyncGenerator

from .base import VisionOperation
from ...helpers.screenshot import capture_screen_or_mouse
from .image_caption import ImageCaptionService


class RapidAPICaptionVision(VisionOperation):
    """Vision operation using RapidAPI Image Caption Generator."""
    
    def __init__(self):
        super().__init__("rapidapi_caption")
        self.api_key = None
        self.caption_service = None
        self.mouse_radius = 200  # Default radius, can be configured
    
    async def start(self):
        await super().start()
        # API key comes from .env
        self.api_key = os.getenv('RAPIDAPI_IMAGE_CAPTION_KEY')
        if self.api_key:
            self.caption_service = ImageCaptionService(self.api_key)
    
    async def close(self):
        await super().close()
        self.caption_service = None
    
    async def configure(self, config_d: Dict[str, Any]):
        """Configure vision operation."""
        self.mouse_radius = config_d.get('mouse_radius', 200)
        # Re-initialize service if API key is available
        if not self.caption_service and self.api_key:
            self.caption_service = ImageCaptionService(self.api_key)
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Returns values of configurable fields."""
        return {
            "mouse_radius": self.mouse_radius
        }
    
    async def _generate(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate vision analysis."""
        screenshot_requested = kwargs.get('screenshot_requested', False)
        use_mouse_area = kwargs.get('vision_use_mouse_area', False)  # From filter
        image_bytes = kwargs.get('image_bytes')
        image_path = kwargs.get('image_path')
        
        # Capture screenshot if requested
        if screenshot_requested and not image_bytes and not image_path:
            image_bytes = capture_screen_or_mouse(
                use_mouse_area=use_mouse_area,
                mouse_radius=self.mouse_radius
            )
        
        # Load from path if provided
        if image_path and not image_bytes:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
        
        if not image_bytes:
            yield {
                "error": "Nenhuma imagem fornecida ou capturada",
                "description": None,
                "image_bytes": None
            }
            return
        
        # Get caption from API
        description = None
        if self.caption_service:
            description = await self.caption_service.caption_image(image_bytes)
        
        # Return result
        result = {
            "description": description,
            "image_bytes": base64.b64encode(image_bytes).decode('utf-8') if image_bytes else None,
            "image_format": "png"
        }
        
        if not description:
            result["error"] = "Falha ao obter descrição da imagem"
        
        yield result

