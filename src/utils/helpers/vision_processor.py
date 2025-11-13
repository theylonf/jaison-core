"""Vision processor - handles screenshot and image recognition."""

import asyncio
from typing import Optional, Dict, Any
from utils.helpers.screenshot import capture_screen_or_mouse
from utils.operations.vision.image_caption import ImageCaptionService


class VisionProcessor:
    """Processes vision requests - takes screenshot and gets description."""
    
    def __init__(self, api_key: str, use_mouse_area: bool = False, mouse_radius: int = 200):
        self.api_key = api_key
        self.use_mouse_area = use_mouse_area
        self.mouse_radius = mouse_radius
        self.caption_service = None
        
        if api_key:
            self.caption_service = ImageCaptionService(api_key)
    
    async def process_vision_request(self, text: str) -> Optional[str]:
        """
        Process vision request if triggered by text.
        
        Args:
            text: User input text
        
        Returns:
            Description of what was seen, or None if not triggered
        """
        # Check if vision is triggered (this will be done by the filter)
        # For now, we'll process if called
        
        if not self.caption_service:
            return None
        
        try:
            # Capture screenshot
            image_bytes = capture_screen_or_mouse(
                use_mouse_area=self.use_mouse_area,
                mouse_radius=self.mouse_radius
            )
            
            if not image_bytes:
                return None
            
            # Get caption from API
            caption = await self.caption_service.caption_image(image_bytes)
            return caption
            
        except Exception as e:
            print(f"Erro ao processar visão: {e}")
            import traceback
            traceback.print_exc()
            return None


