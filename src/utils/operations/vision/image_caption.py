"""Image caption service using RapidAPI."""

import base64
import json
from typing import Dict, Any, Optional
import httpx
from io import BytesIO
from PIL import Image


class ImageCaptionService:
    """Service for image recognition using RapidAPI Image Caption Generator."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://image-caption-generator2.p.rapidapi.com"
        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "image-caption-generator2.p.rapidapi.com",
            "Content-Type": "application/json"
        }
    
    async def caption_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Generate caption for image.
        
        Args:
            image_bytes: Image as PNG/JPEG bytes
        
        Returns:
            Caption string or None if error
        """
        try:
            # Compress and resize image before sending to API
            # This reduces the payload size and avoids API errors
            try:
                # Open image from bytes
                img = Image.open(BytesIO(image_bytes))
                
                # Resize if too large (max 1024x768 for API compatibility, maintain aspect ratio)
                # Smaller size to avoid API errors
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
                # Target: keep under 200KB raw (~270KB base64) to avoid API errors
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
                
                image_bytes = compressed_bytes
            except Exception as e:
                print(f"[Vision] Aviso: Não foi possível comprimir imagem, usando original: {e}")
                # Continue with original image if compression fails
            
            # Convert image to base64 string (without data URL prefix)
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # API endpoint for base64 images
            url = f"{self.base_url}/v2/captions/base64"
            
            # Payload as per API documentation
            payload = {
                "data": image_base64
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    # API returns: {"captions": ["caption1", "caption2", ...]}
                    if isinstance(result, dict) and "captions" in result:
                        captions = result.get("captions", [])
                        if captions and len(captions) > 0:
                            # Return the first caption
                            return captions[0]
                        else:
                            print("Erro na API de reconhecimento de imagem: Array de captions vazio")
                            return None
                    else:
                        print(f"Erro na API de reconhecimento de imagem: Formato de resposta inesperado: {result}")
                        return None
                else:
                    error_text = response.text
                    print(f"Erro na API de reconhecimento de imagem: {response.status_code} - {error_text}")
                    return None
                    
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
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

