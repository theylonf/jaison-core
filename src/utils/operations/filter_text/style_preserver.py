'''
Filtro que preserva tags de estilo de voz entre colchetes [estilo] no texto
para que possam ser processadas pelo TTS antes de serem removidas.
Útil para garantir que estilos sejam detectados mesmo após outros filtros.
'''

import re
from .base import FilterTextOperation

class StylePreserverFilter(FilterTextOperation):
    def __init__(self):
        super().__init__("style_preserver")
        self.style_pattern = None
        
    async def start(self):
        await super().start()
        # Lista de estilos suportados pelo Azure TTS
        self.valid_styles = [
            "excited", "cheerful", "sad", "angry", "fearful", "disgruntled",
            "serious", "affectionate", "gentle", "lyrical", "newscast",
            "customerservice", "empathetic", "calm", "hopeful", "shouting",
            "whispering", "terrified", "unfriendly", "friendly", "poetry-reading"
        ]
        # Padrão simples para encontrar qualquer coisa entre colchetes
        # Validação será feita depois
        self.style_pattern = re.compile(r'\[([^\]]+)\]', re.IGNORECASE)
        
    async def close(self):
        await super().close()
        self.style_pattern = None
    
    async def configure(self, config_d):
        '''Configure and validate operation-specific configuration'''
        return
        
    async def get_configuration(self):
        '''Returns values of configurable fields'''
        return {}

    async def _generate(self, content: str = None, **kwargs):
        '''
        Preserva tags de estilo no texto e adiciona informação sobre estilos detectados
        '''
        # Encontra todos os blocos entre colchetes no texto
        style_matches = self.style_pattern.findall(content)
        detected_styles = []
        
        if style_matches:
            # Processa cada match para extrair estilos válidos
            for match in style_matches:
                # Divide por vírgula e processa cada possível estilo
                possible_styles = [s.strip().lower() for s in match.split(',')]
                
                # Verifica se algum dos estilos está na lista de válidos
                for style in possible_styles:
                    if style in self.valid_styles:
                        detected_styles.append(style)
                        break  # Usa apenas o primeiro estilo válido de cada bloco
        
        output = {
            "content": content
        }
        
        # Adiciona informação sobre estilos detectados (primeiro estilo encontrado)
        if detected_styles:
            output["detected_style"] = detected_styles[0]
            # Também adiciona lista completa de estilos
            output["detected_styles"] = detected_styles
        
        yield output

