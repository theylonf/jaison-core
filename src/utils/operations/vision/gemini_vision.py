"""Google Gemini vision operation."""

import os
import base64
from typing import Dict, Any, AsyncGenerator

from .base import VisionOperation
from ...helpers.screenshot import capture_screen_or_mouse
from .gemini_caption import GeminiImageCaptionService


class GeminiVision(VisionOperation):
    """Vision operation using Google Gemini API."""
    
    def __init__(self):
        super().__init__("gemini_vision")
        self.api_key = None
        self.model = "gemini-2.5-flash"  # Default model with vision support (stable, not discontinued)
        self.caption_service = None
        self.mouse_radius = 200  # Default radius, can be configured
    
    async def start(self):
        await super().start()
        # API key comes from .env or environment variable
        self.api_key = os.getenv('GEMINI_API_KEY')
        if self.api_key:
            try:
                self.caption_service = GeminiImageCaptionService(
                    api_key=self.api_key,
                    model=self.model
                )
                print(f"[Vision] Gemini inicializado com sucesso (modelo: {self.model})")
            except ImportError as e:
                print(f"[Vision] Erro ao inicializar Gemini: {e}")
                print("[Vision] Instale com: pip install google-genai")
                print("[Vision] Servidor continuará sem funcionalidade de visão")
            except Exception as e:
                print(f"[Vision] Erro ao inicializar Gemini: {e}")
                print("[Vision] Servidor continuará sem funcionalidade de visão")
        else:
            print("[Vision] Aviso: GEMINI_API_KEY não encontrada no ambiente")
            print("[Vision] Servidor continuará sem funcionalidade de visão")
    
    async def close(self):
        await super().close()
        self.caption_service = None
    
    async def configure(self, config_d: Dict[str, Any]):
        """Configure vision operation."""
        self.mouse_radius = config_d.get('mouse_radius', 200)
        self.model = config_d.get('model', "gemini-2.0-flash-exp")
        
        # Re-initialize service if API key is available
        if not self.caption_service and self.api_key:
            try:
                self.caption_service = GeminiImageCaptionService(
                    api_key=self.api_key,
                    model=self.model
                )
            except ImportError as e:
                print(f"[Vision] Erro ao inicializar Gemini: {e}")
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Returns values of configurable fields."""
        return {
            "mouse_radius": self.mouse_radius,
            "model": self.model
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
        
        # Enviar imagem imediatamente após captura (antes de chamar API)
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        yield {
            "description": None,  # Ainda não temos a descrição
            "image_bytes": image_base64,
            "image_format": "png",
            "processing": True  # Indica que ainda está processando
        }
        
        # Get caption from API (pode demorar)
        description = None
        if self.caption_service:
            try:
                description = await self.caption_service.caption_image(image_bytes)
            except Exception as api_error:
                # Se a API lançou exceção (erro temporário), propagar para acionar fallback
                # A imagem já foi enviada, então não precisamos fazer nada aqui
                # A exceção será capturada pelo fallback handler
                raise
        else:
            yield {
                "error": "Serviço Gemini não inicializado. Verifique se GEMINI_API_KEY está configurada.",
                "description": None,
                "image_bytes": image_base64,
                "image_format": "png",
                "processing": False
            }
            return
        
        # Se chegou aqui sem exceção mas description é None, pode ser erro definitivo
        # Mas ainda assim retornamos o resultado para não quebrar o fluxo
        result = {
            "description": description,
            "image_bytes": image_base64,  # Manter a mesma imagem
            "image_format": "png",
            "processing": False  # Processamento concluído
        }
        
        if not description:
            result["error"] = "Falha ao obter descrição da imagem"
        
        yield result

