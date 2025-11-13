"""Base class for vision operations."""

from typing import Dict, Any, AsyncGenerator

from ..base import Operation


class VisionOperation(Operation):
    """Base class for vision/image recognition operations."""
    
    def __init__(self, op_id: str):
        super().__init__("VISION", op_id)
    
    async def _parse_chunk(self, chunk_in: Dict[str, Any]) -> Dict[str, Any]:
        """Extract information from input for use in _generate."""
        assert "image_bytes" in chunk_in or "image_path" in chunk_in or "screenshot_requested" in chunk_in
        return chunk_in
    
    async def _generate(self, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate output stream."""
        raise NotImplementedError


