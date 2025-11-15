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
            # Padrões para "o que está/tem/há" + localização do mouse (incluindo "em cima", "sobre", etc.)
            r'\b(o que|oq|que)\s+(tem|há|está|esta)\s+(aqui no mouse|aqui no meu mouse|no mouse|no meu mouse|ao redor do mouse|em cima do mouse|em cima do meu mouse|sobre o mouse|sobre o meu mouse)\b',
            # Padrão mais flexível: "o que tem/está" + "aqui/aí" + "em cima/sobre/no" + "do mouse"
            r'\b(o que|oq|que)\s+(tem|há|está|esta).*?(aqui|aí).*?(em cima|sobre|no|ao redor|em volta).*?(do|do meu)\s+(mouse|cursor|ponteiro)\b',
            r'\b(o que|oq|que)\s+(está|esta).*?(em cima|sobre|no|ao redor|em volta).*?(do|do meu)\s+(mouse|cursor|ponteiro)\b',
            r'\b(consegue|pode|podes|podia)\s+(falar|dizer|me dizer|me falar|ver|vê|vê aqui|ve aqui|olhar|olha|mostrar|mostra).*?\b(o que|oq|que)\s+(tem|há|está|esta).*?(aqui|aí|em cima|sobre|no|ao redor|em volta).*?(do|do meu)\s+(mouse|cursor|ponteiro)\b',
            r'\b(at|around|near|above|on top of)\s+(my|the)\s+(mouse|cursor|pointer)\b',
            r'\b(mouse|cursor|pointer)\s+(area|region|here|around)\b',
            r'\b(what|what\'s|whats)\s+(do you|you|u)\s+(see|seeing)\s+(at|around|near|above|on top of)\s+(my|the)\s+(mouse|cursor|pointer)\b',
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
        # IMPORTANTE: Usar \b (word boundaries) apenas onde necessário para evitar matches parciais
        # Exemplo: "ha" sem \b corresponderia a "acha", então usamos apenas "tem" e "há" com \b
        generic_patterns = [
            # Padrões com "na tela" ou "na minha tela" (mais específicos primeiro)
            # Usar grupos mais flexíveis para permitir variações
            r'\b(o que|oq|que)\b.*?\b(você|vc|voce|tu)\b.*?\b(vê|ve|vê aqui|ve aqui|olha|olha aqui|está vendo|esta vendo|vendo)\b.*?(na|na minha|na sua).*?tela',
            r'\b(o que|oq|que)\b.*?\b(você|vc|voce|tu)\b.*?\b(vê|ve|vê aqui|ve aqui|olha|olha aqui|está vendo|esta vendo|vendo)\b',
            # Padrão mais específico: requer "tem/há" como palavra completa + contexto de localização
            # NOTA: Não usar "ha" sem acento para evitar match em "acha"
            # IMPORTANTE: Excluir menções a mouse para evitar conflito com padrões de mouse
            r'\b(o que|oq|que)\b.*?\b(tem|há)\b.*?(aqui|aí|nesse lugar|neste lugar|na tela|na minha tela)(?!.*?\b(mouse|cursor|ponteiro)\b)',
            # Padrões com verbos de ação explícitos
            r'\b(olha|olhe|veja|vê|ve)\b.*?(aqui|aí|na tela|na minha tela|a tela)',
            r'\b(mostra|mostre|mostrar)\b.*?\b(o que|oq|que)\b.*?\b(tem|há|está|esta)\b.*?(aqui|aí|na tela|na minha tela)',
            r'\b(descreve|descreva|descrever)\b.*?\b(o que|oq|que)\b.*?\b(você|vc|voce|tu)\b.*?\b(vê|ve|está vendo|esta vendo|vendo)\b.*?(na|na minha|na sua)?.*?tela',
            r'\b(analisa|analise|analisar)\b.*?(aqui|aí|isso|isto|a tela|a minha tela)',
            # Padrões em inglês
            r'\b(what|what\'s|whats)\b.*?\b(do you|you|u)\b.*?\b(see|seeing|look at|looking at)\b.*?(here|this|on screen|on my screen)',
            r'\b(look|looks|looking)\b.*?(here|at this|at my screen)',
            r'\b(describe|describes|describing)\b.*?\b(what|what\'s|whats)\b.*?\b(you|u)\b.*?\b(see|seeing)\b.*?(on|on my|on the)?.*?screen',
            r'\b(analyze|analyzes|analyzing)\b.*?(this|here|my screen)',
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
            
            # PRIORIDADE 1: Check for mouse area patterns FIRST (mouse always has priority over screen)
            # This ensures that if both mouse and screen patterns match, mouse wins
            for pattern in self.mouse_patterns_compiled:
                if pattern.search(content_lower):
                    self.triggered = True
                    use_mouse_area = True
                    break  # Stop checking other patterns once mouse is detected
            
            # PRIORIDADE 2: If not mouse, check for screen patterns
            if not self.triggered:
                for pattern in self.screen_patterns_compiled:
                    if pattern.search(content_lower):
                        self.triggered = True
                        use_mouse_area = False
                        break  # Stop checking other patterns once screen is detected
            
            # PRIORIDADE 3: If still not triggered, check generic patterns (assume full screen)
            if not self.triggered:
                for pattern in self.generic_patterns_compiled:
                    if pattern.search(content_lower):
                        self.triggered = True
                        use_mouse_area = False  # Generic = full screen
                        break  # Stop checking once a pattern matches
        
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

