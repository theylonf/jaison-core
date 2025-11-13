"""Vision trigger filter - detects keywords that trigger image recognition."""

import re
from typing import Dict, Any, AsyncGenerator

from .base import FilterTextOperation


class VisionTriggerFilter(FilterTextOperation):
    """Detects keywords that indicate user wants to see something on screen."""
    
    def __init__(self):
        super().__init__("vision_trigger")
        self.trigger_patterns = None
        self.triggered = False
        
    async def start(self):
        await super().start()
        
        # Padrões específicos para área do mouse (mais específicos primeiro)
        mouse_patterns = [
            r'\b(no|no meu|no meu mouse|aqui no mouse|aqui no meu mouse|ao redor do mouse|ao redor do meu mouse|em volta do mouse|em volta do meu mouse)\s+(mouse|cursor|ponteiro)\b',
            r'\b(mouse|cursor|ponteiro)\s+(aqui|aí|ai|no mouse|no meu mouse|ao redor|em volta)\b',
            r'\b(olha|olhe|veja|vê|ve|mostra|mostre)\s+(aqui no mouse|aqui no meu mouse|no mouse|no meu mouse|ao redor do mouse|ao redor do meu mouse|em volta do mouse)\b',
            r'\b(o que|oq|que)\s+(tem|há|ha|está|esta)\s+(aqui no mouse|aqui no meu mouse|no mouse|no meu mouse|ao redor do mouse)\b',
            r'\b(at|around|near)\s+(my|the)\s+(mouse|cursor|pointer)\b',
            r'\b(mouse|cursor|pointer)\s+(area|region|here|around)\b',
            r'\b(what|what\'s|whats)\s+(do you|you|u)\s+(see|seeing)\s+(at|around|near)\s+(my|the)\s+(mouse|cursor|pointer)\b',
        ]
        self.mouse_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in mouse_patterns]
        
        # Padrões específicos para tela inteira
        screen_patterns = [
            r'\b(na|na minha|na tela|na minha tela|tela inteira|tela completa|toda a tela|toda tela|tela toda)\s+(tela|screen)\b',
            r'\b(tela|screen)\s+(inteira|completa|toda|minha|aqui|aí|ai)\b',
            r'\b(olha|olhe|veja|vê|ve|mostra|mostre)\s+(a tela|a minha tela|na tela|na minha tela|tela inteira|tela completa)\b',
            r'\b(o que|oq|que)\s+(tem|há|ha|está|esta)\s+(na tela|na minha tela|na sua tela|na tela toda)\b',
            r'\b(on|on my|on the)\s+(screen|display|monitor)\b',
            r'\b(screen|display|monitor)\s+(here|now|what|entire|full|whole)\b',
            r'\b(what|what\'s|whats)\s+(do you|you|u)\s+(see|seeing)\s+(on|on my|on the)\s+(screen|display|monitor)\b',
            r'\b(entire|full|whole)\s+(screen|display|monitor)\b',
        ]
        self.screen_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in screen_patterns]
        
        # Padrões genéricos (assumem tela inteira por padrão)
        generic_patterns = [
            # Padrões com "na tela" ou "na minha tela" (mais específicos primeiro)
            # Usa .*? para permitir palavras entre os termos e não requer word boundary no final
            r'(o que|oq|que).*?(você|vc|voce|tu).*?(vê|ve|vê aqui|ve aqui|olha|olha aqui|está vendo|esta vendo|vendo).*?(na|na minha|na sua).*?tela',
            r'(o que|oq|que).*?(você|vc|voce|tu).*?(vê|ve|vê aqui|ve aqui|olha|olha aqui|está vendo|esta vendo|vendo)',
            r'(o que|oq|que).*?(tem|há|ha).*?(aqui|aí|ai|nesse lugar|neste lugar|na tela|na minha tela)',
            r'(olha|olhe|veja|vê|ve).*?(aqui|aí|ai|na tela|na minha tela)',
            r'(mostra|mostre|mostrar).*?(o que|oq|que).*?(tem|há|ha|está|esta).*?(aqui|aí|ai|na tela|na minha tela)',
            r'(descreve|descreva|descrever).*?(o que|oq|que).*?(você|vc|voce|tu).*?(vê|ve|está vendo|esta vendo|vendo).*?(na|na minha|na sua)?.*?tela',
            r'(analisa|analise|analisar).*?(aqui|aí|ai|isso|isto|a tela|a minha tela)',
            r'(what|what\'s|whats).*?(do you|you|u).*?(see|seeing|look at|looking at).*?(here|this|on screen|on my screen)',
            r'(look|looks|looking).*?(here|at this|at my screen)',
            r'(describe|describes|describing).*?(what|what\'s|whats).*?(you|u).*?(see|seeing).*?(on|on my|on the)?.*?screen',
            r'(analyze|analyzes|analyzing).*?(this|here|my screen)',
        ]
        self.generic_patterns_compiled = [re.compile(pattern, re.IGNORECASE) for pattern in generic_patterns]
        
    async def close(self):
        await super().close()
    
    async def configure(self, config_d: Dict[str, Any]):
        """Configure and validate operation-specific configuration."""
        return
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Returns values of configurable fields."""
        return {}
    
    async def _generate(self, content: str = None, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate output stream with vision trigger flag and capture mode."""
        self.triggered = False
        use_mouse_area = False  # Default: tela inteira
        
        if content:
            content_lower = content.lower()
            
            # Check for mouse area patterns first (more specific)
            for pattern in self.mouse_patterns_compiled:
                if pattern.search(content_lower):
                    self.triggered = True
                    use_mouse_area = True
                    break
            
            # If not mouse, check for screen patterns
            if self.triggered == False:
                for pattern in self.screen_patterns_compiled:
                    if pattern.search(content_lower):
                        self.triggered = True
                        use_mouse_area = False
                        break
            
            # If still not triggered, check generic patterns (assume full screen)
            if self.triggered == False:
                for pattern in self.generic_patterns_compiled:
                    if pattern.search(content_lower):
                        self.triggered = True
                        use_mouse_area = False  # Generic = full screen
                        break
        
        result = {
            "content": content,
            "vision_triggered": self.triggered,
            "vision_use_mouse_area": use_mouse_area
        }
        
        # Preserve other fields
        for key, value in kwargs.items():
            if key not in result:
                result[key] = value
        
        yield result

