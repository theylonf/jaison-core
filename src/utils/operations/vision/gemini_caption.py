"""Image caption service using Google Gemini API."""

import base64
import os
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    types = None


class GeminiImageCaptionService:
    """Service for image recognition using Google Gemini API."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        """
        Initialize Gemini image caption service.
        
        Args:
            api_key: Google Gemini API key
            model: Model to use (default: gemini-2.5-flash for vision)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai não está instalado. Instale com: pip install google-genai")
        
        self.api_key = api_key
        self.model = model
        # Fallback models to try if primary model fails (503, 404, etc.)
        # Ordered by preference: faster/cheaper first, then more powerful
        self.fallback_models = [
            "gemini-2.0-flash",      # Alternative fast model
            "gemini-2.0-flash-lite", # Lightweight option
            "gemini-2.5-pro",        # More powerful fallback
        ]
        # Initialize client - API key can be passed or set via environment variable
        # According to docs, if GEMINI_API_KEY env var is set, it's used automatically
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            # Try to use environment variable
            self.client = genai.Client()
    
    def _optimize_image(self, image_bytes: bytes) -> bytes:
        """
        Optimize image by resizing and compressing.
        
        Args:
            image_bytes: Original image bytes
        
        Returns:
            Optimized image bytes
        """
        try:
            # Open image from bytes
            img = Image.open(BytesIO(image_bytes))
            
            # Resize if too large (max 1024x768 for API compatibility, maintain aspect ratio)
            max_width = 1024
            max_height = 768
            original_size = len(image_bytes)
            print(f"[Vision] Imagem original: {img.width}x{img.height}, {original_size} bytes")
            
            if img.width > max_width or img.height > max_height:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                print(f"[Vision] Imagem redimensionada para: {img.width}x{img.height}")
            
            # Convert to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Compress as JPEG with progressive quality reduction
            # Target: keep under 200KB raw (~270KB base64) to optimize API calls
            compressed_bytes = None
            for quality in [70, 60, 50, 40]:
                output = BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                test_bytes = output.getvalue()
                if len(test_bytes) < 200000:  # 200KB raw
                    compressed_bytes = test_bytes
                    print(f"[Vision] Qualidade {quality} atingiu tamanho desejado: {len(test_bytes)} bytes")
                    break
            
            # If still too large, use lowest quality and further resize
            if compressed_bytes is None:
                # Resize even more aggressively
                if img.width > 800 or img.height > 600:
                    img.thumbnail((800, 600), Image.Resampling.LANCZOS)
                    print(f"[Vision] Redimensionamento adicional para: {img.width}x{img.height}")
                
                output = BytesIO()
                img.save(output, format='JPEG', quality=35, optimize=True)
                compressed_bytes = output.getvalue()
                print(f"[Vision] Usando qualidade mínima (35): {len(compressed_bytes)} bytes")
            
            # Log compression ratio
            compressed_size = len(compressed_bytes)
            compression_ratio = (1 - compressed_size / original_size) * 100
            base64_size = len(base64.b64encode(compressed_bytes).decode('utf-8'))
            print(f"[Vision] Imagem comprimida: {original_size} bytes -> {compressed_size} bytes ({compression_ratio:.1f}% redução, base64: {base64_size} bytes)")
            
            return compressed_bytes
        except Exception as e:
            print(f"[Vision] Aviso: Não foi possível comprimir imagem, usando original: {e}")
            # Continue with original image if compression fails
            return image_bytes
    
    async def caption_image(self, image_bytes: bytes, prompt: str = "Descreva detalhadamente o que você vê nesta imagem em português.") -> Optional[str]:
        """
        Generate caption for image using Gemini API.
        
        Args:
            image_bytes: Image as PNG/JPEG bytes
            prompt: Prompt to guide the image analysis
        
        Returns:
            Caption string or None if error
        """
        if not GEMINI_AVAILABLE:
            print("[Vision] Erro: google-genai não está instalado")
            return None
        
        try:
            # Optimize image before sending
            optimized_bytes = self._optimize_image(image_bytes)
            
            # Convert image to base64
            image_base64 = base64.b64encode(optimized_bytes).decode('utf-8')
            
            # Determine MIME type based on image format
            # Try to detect from original bytes
            mime_type = "image/jpeg"  # Default
            try:
                img = Image.open(BytesIO(optimized_bytes))
                if img.format == "PNG":
                    mime_type = "image/png"
                elif img.format == "JPEG":
                    mime_type = "image/jpeg"
            except:
                pass
            
            # Create content with image and text prompt
            # According to Gemini API documentation, we can use dict format or types
            # Using dict format which is simpler and works with the SDK
            contents = [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
            
            # Call Gemini API with fallback to other models if needed
            # The SDK accepts contents as a list of dicts for multimodal content
            # Reference: https://ai.google.dev/gemini-api/docs/image-understanding
            # The SDK has built-in retry logic for rate limits
            
            # List of models to try (primary + fallbacks)
            models_to_try = [self.model] + [m for m in self.fallback_models if m != self.model]
            last_error = None
            response = None
            
            for model_name in models_to_try:
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    # Success! Break out of loop
                    if model_name != self.model:
                        print(f"[Vision] ✅ Modelo alternativo usado com sucesso: {model_name} (modelo principal {self.model} falhou)")
                    break
                except Exception as api_error:
                    error_str = str(api_error)
                    last_error = api_error
                    
                    # Check for errors that should trigger fallback
                    should_fallback = (
                        "503" in error_str or "UNAVAILABLE" in error_str or "overloaded" in error_str.lower() or
                        "404" in error_str or "NOT_FOUND" in error_str or "not found" in error_str.lower()
                    )
                    
                    # If this is the last model to try, handle the error
                    if model_name == models_to_try[-1] or not should_fallback:
                        # Handle specific error types that shouldn't trigger fallback
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                            print("[Vision] ⚠️ Quota da API Gemini excedida")
                            print("[Vision] 💡 Informações sobre limites de taxa:")
                            print("[Vision]   📊 Verifique seu uso: https://ai.dev/usage?tab=rate-limit")
                            print("[Vision]   📖 Documentação: https://ai.google.dev/gemini-api/docs/rate-limits")
                            print("[Vision]   🔄 Limites do nível gratuito (segundo documentação oficial):")
                            print("[Vision]      - Gemini 2.5 Flash: 10 RPM, 250.000 TPM, 250 RPD")
                            print("[Vision]      - Gemini 2.0 Flash: 15 RPM, 1.000.000 TPM, 200 RPD")
                            print("[Vision]      - Gemini 2.5 Pro: 2 RPM, 125.000 TPM, 50 RPD")
                            print("[Vision]   ⚠️ Nota: Gemini 1.5 Flash foi descontinuado")
                            print("[Vision]   ⏳ Aguarde alguns minutos antes de tentar novamente")
                            print("[Vision]   💳 Para limites maiores, considere fazer upgrade do nível de uso")
                            return None
                        elif "401" in error_str or "authentication" in error_str.lower() or "API key" in error_str:
                            print("[Vision] ⚠️ Erro de autenticação na API Gemini")
                            print("[Vision] 💡 Verifique se GEMINI_API_KEY está configurada corretamente no arquivo .env")
                            return None
                        elif should_fallback:
                            # Last model failed with 503/404, show error
                            if "503" in error_str or "UNAVAILABLE" in error_str:
                                print(f"[Vision] ⚠️ Todos os modelos tentados ({len(models_to_try)}) estão indisponíveis")
                                print("[Vision] 💡 O serviço Gemini está sobrecarregado no momento")
                                print("[Vision]   ⏳ Tente novamente em alguns segundos")
                            elif "404" in error_str or "NOT_FOUND" in error_str:
                                print("[Vision] ⚠️ Modelo não encontrado na API Gemini")
                                print("[Vision] 💡 Modelos disponíveis com suporte a visão:")
                                print("[Vision]      - gemini-2.5-flash (recomendado - estável)")
                                print("[Vision]      - gemini-2.5-pro (mais poderoso)")
                                print("[Vision]      - gemini-2.0-flash (alternativa)")
                                print("[Vision]      - gemini-2.0-flash-lite (mais leve)")
                                print("[Vision]   📖 Consulte: https://ai.google.dev/gemini-api/docs/models")
                            return None
                        else:
                            # Re-raise other errors to be handled by outer try/except
                            raise
                    else:
                        # Try next fallback model
                        print(f"[Vision] ⚠️ Modelo {model_name} falhou, tentando modelo alternativo...")
                        continue
            
            # If we get here without breaking, all models failed
            if response is None:
                if last_error:
                    # This shouldn't happen as errors are handled in the loop, but just in case
                    raise last_error
                print("[Vision] ⚠️ Todos os modelos falharam")
                return None
            
            # Extract text from response
            # The response object should have a .text attribute
            try:
                if hasattr(response, 'text') and response.text:
                    return response.text.strip()
                
                # Alternative: check candidates structure
                if hasattr(response, 'candidates') and response.candidates:
                    for candidate in response.candidates:
                        if hasattr(candidate, 'content'):
                            content = candidate.content
                            if hasattr(content, 'parts'):
                                for part in content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        return part.text.strip()
                            elif hasattr(content, 'text') and content.text:
                                return content.text.strip()
                
                # Last resort: try to get text directly from response
                if hasattr(response, 'text'):
                    text = getattr(response, 'text', None)
                    if text:
                        return str(text).strip()
                
                print("[Vision] Erro: Resposta da API Gemini não contém texto")
                print(f"[Vision] Debug: Tipo de resposta: {type(response)}, Atributos: {dir(response)}")
                return None
            except Exception as e:
                print(f"[Vision] Erro ao extrair texto da resposta: {e}")
                import traceback
                traceback.print_exc()
                return None
                    
        except Exception as e:
            # Only print full traceback for unexpected errors (not quota/auth/503/404 errors already handled)
            error_str = str(e)
            if ("429" not in error_str and "RESOURCE_EXHAUSTED" not in error_str and 
                "401" not in error_str and "503" not in error_str and "UNAVAILABLE" not in error_str and
                "404" not in error_str and "NOT_FOUND" not in error_str):
                print(f"[Vision] Erro ao processar imagem com Gemini: {e}")
                import traceback
                traceback.print_exc()
            return None
    
    async def analyze_image(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Analyze image and return detailed description.
        
        Args:
            image_bytes: Image as PNG/JPEG bytes
        
        Returns:
            Dictionary with analysis or None if error
        """
        caption = await self.caption_image(image_bytes)
        if caption:
            return {
                "caption": caption,
                "description": caption
            }
        return None

