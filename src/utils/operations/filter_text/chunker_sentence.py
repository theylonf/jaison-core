import spacy

from utils.config import Config

from .base import FilterTextOperation

class SentenceChunkerFilter(FilterTextOperation):
    def __init__(self):
        super().__init__("chunker_sentence")
        self.nlp = None
        
    async def start(self):
        await super().start()
        self.nlp = spacy.load(Config().spacy_model)
        
    async def close(self):
        await super().close()
        self.nlp = None
    
    async def configure(self, config_d):
        '''Configure and validate operation-specific configuration'''
        return
        
    async def get_configuration(self):
        '''Returns values of configurable fields'''
        return {}

    async def _generate(self, content: str = None, **kwargs):
        '''Generate a output stream'''
        import re
        
        # Lista de estilos suportados (para filtrar antes de processar)
        valid_styles = [
            "excited", "cheerful", "sad", "angry", "fearful", "disgruntled",
            "serious", "affectionate", "gentle", "lyrical", "newscast",
            "customerservice", "empathetic", "calm", "hopeful", "shouting",
            "whispering", "terrified", "unfriendly", "friendly", "poetry-reading"
        ]
        
        # Padrão para encontrar TODOS os blocos entre colchetes (não apenas estilos válidos)
        # Isso remove qualquer coisa entre colchetes, incluindo estilos inválidos como [sedutora]
        all_brackets_pattern = re.compile(r'\[([^\]]+)\]', re.IGNORECASE)
        
        # Extrai estilos válidos antes de remover
        detected_styles = []
        style_matches = all_brackets_pattern.findall(content)
        
        for match in style_matches:
            # Divide por vírgula e processa cada possível estilo
            possible_styles = [s.strip().lower() for s in match.split(',')]
            for style in possible_styles:
                if style in valid_styles:
                    detected_styles.append(style)
                    break  # Usa apenas o primeiro estilo válido de cada bloco
        
        # Remove TODOS os blocos entre colchetes do texto (válidos ou não)
        # Isso evita que estilos sejam tratados como sentenças separadas
        content_without_styles = all_brackets_pattern.sub('', content).strip()
        
        # Se o conteúdo sem estilos estiver vazio ou for muito curto, não processa
        if not content_without_styles or len(content_without_styles) < 2:
            # Se havia estilos mas não há conteúdo, não envia nada
            return
        
        # Processa sentenças
        sentences = [sent.text.strip() for sent in self.nlp(content_without_styles).sents]
        
        # Filtra sentenças vazias ou muito curtas (que podem ser apenas pontuação)
        filtered_sentences = [s for s in sentences if len(s) > 1 and not s.isspace()]
        
        # Se não há sentenças válidas, não envia nada
        if not filtered_sentences:
            return
    
        # Aplica o estilo detectado apenas à última sentença (onde geralmente está o estilo)
        for i, s in enumerate(filtered_sentences):
            output = {"content": s}
            
            # Preserva informações de estilo se vierem de filtros anteriores
            if "detected_style" in kwargs:
                output["detected_style"] = kwargs["detected_style"]
            elif detected_styles and i == len(filtered_sentences) - 1:
                # Aplica estilo apenas à última sentença
                output["detected_style"] = detected_styles[0]
            
            # Preserva outras informações dos filtros anteriores
            for key in ["emotion", "detected_styles"]:
                if key in kwargs:
                    output[key] = kwargs[key]
            
            yield output

