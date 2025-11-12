import os
import wave
import re
from io import BytesIO
from typing import Tuple
import azure.cognitiveservices.speech as speechsdk

from utils.config import Config

from .base import TTSOperation

class AzureTTS(TTSOperation):
    # Lista de estilos suportados pela Azure TTS
    SUPPORTED_STYLES = [
        "excited", "cheerful", "sad", "angry", "fearful", "disgruntled",
        "serious", "affectionate", "gentle", "lyrical", "newscast",
        "customerservice", "empathetic", "calm", "hopeful", "shouting",
        "whispering", "terrified", "unfriendly", "friendly", "poetry-reading"
    ]
    
    # Mapeamento de estilos de voz para emoções do VTube Studio (baseado em emotion_roberta)
    # Emoções VTS: admiration, amusement, approval, caring, desire, excitement, gratitude, joy, love, optimism, pride,
    #              anger, annoyance, disappointment, disapproval, embarrassment, fear, disgust, grief, nervousness, remorse, sadness,
    #              confusion, curiosity, realization, relief, surprise, neutral
    STYLE_TO_VTS_EMOTION = {
        "excited": "excitement",
        "cheerful": "joy",
        "sad": "sadness",
        "angry": "anger",
        "fearful": "fear",
        "disgruntled": "annoyance",
        "serious": "neutral",
        "affectionate": "love",
        "gentle": "caring",
        "lyrical": "joy",
        "newscast": "neutral",
        "customerservice": "neutral",
        "empathetic": "caring",
        "calm": "relief",
        "hopeful": "optimism",
        "shouting": "anger",
        "whispering": "nervousness",
        "terrified": "fear",
        "unfriendly": "disapproval",
        "friendly": "approval",
        "poetry-reading": "joy"
    }
    
    def __init__(self):
        super().__init__("azure")
        self.client = None
        
        self.voice: str = "en-US-AshleyNeural"
        self.style: str = None  # Estilo padrão da configuração
        self.language: str = None
        
    async def start(self) -> None:
        '''General setup needed to start generated'''
        await super().start()
        
        self.speech_config = speechsdk.SpeechConfig(
            region=os.environ.get('AZURE_REGION'),
            subscription=os.getenv("AZURE_API_KEY")
        )
        self.speech_config.speech_synthesis_voice_name = self.voice
        self.speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)
        # set timeout value to bigger ones to avoid sdk cancel the request when GPT latency too high
        self.speech_config.set_property(speechsdk.PropertyId.SpeechSynthesis_FrameTimeoutInterval, "100000000")
        self.speech_config.set_property(speechsdk.PropertyId.SpeechSynthesis_RtfTimeoutThreshold, "10")
        
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=self.speech_config, audio_config=None)
                
    async def configure(self, config_d):
        '''Configure and validate operation-specific configuration'''
        if "voice" in config_d: self.voice = str(config_d['voice'])
        if "style" in config_d: self.style = str(config_d['style'])
        if "language" in config_d: self.language = str(config_d['language'])
        
        assert self.voice is not None and len(self.voice) > 0
        
    async def get_configuration(self):
        '''Returns values of configurable fields'''
        return {
            "voice": self.voice,
            "style": self.style,
            "language": self.language
        }
    
    def _get_language_code(self) -> str:
        '''Get language code from config or extract from voice name'''
        if self.language:
            return self.language
        # Extract language from voice name (e.g., "zh-CN" from "zh-CN-XiaoxiaoMultilingualNeural")
        lang = self.voice.split('-')[:2]
        lang_code = '-'.join(lang) if len(lang) >= 2 else "en-US"
        return lang_code
    
    def _build_ssml(self, content: str, style: str = None) -> str:
        '''
        Build SSML string with style and language if configured
        Args:
            content: Texto para síntese
            style: Estilo a ser usado (se None, usa self.style padrão)
        '''
        lang_code = self._get_language_code()
        style_to_use = style if style else self.style
        
        # Build SSML with style if configured
        if style_to_use:
            ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{lang_code}">
  <voice name="{self.voice}">
    <mstts:express-as style="{style_to_use}">
      {self._escape_xml(content)}
    </mstts:express-as>
  </voice>
</speak>'''
        # Build SSML with language only (for multilingual models)
        elif self.language:
            ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang_code}">
  <voice name="{self.voice}">
    {self._escape_xml(content)}
  </voice>
</speak>'''
        else:
            return content
        
        return ssml
    
    def _extract_style_from_text(self, text: str) -> Tuple[str, str]:
        '''
        Extrai estilos entre colchetes [ ] do texto e retorna (texto_limpo, estilo_detectado)
        Exemplo: "Olá! [excited, cheerful]" -> ("Olá! ", "excited")
        Remove TODOS os blocos entre colchetes, mas apenas detecta estilos válidos
        '''
        detected_style = None
        cleaned_text = text
        
        # Padrão para encontrar TODOS os blocos entre colchetes
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, text)
        
        for match in matches:
            # Divide por vírgula e processa cada possível estilo
            possible_styles = [s.strip().lower() for s in match.split(',')]
            
            # Verifica se algum dos estilos está na lista de suportados
            for style in possible_styles:
                if style in self.SUPPORTED_STYLES:
                    if not detected_style:  # Usa apenas o primeiro estilo válido encontrado
                        detected_style = style
                    break
            
            # Remove TODOS os blocos entre colchetes do texto (válidos ou não)
            escaped_match = re.escape(match)
            cleaned_text = re.sub(r'\[' + escaped_match + r'\]', '', cleaned_text, count=1)
        
        # Remove espaços extras que possam ter ficado e limpa pontuação duplicada
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        cleaned_text = re.sub(r'\s+([,.!?;:])', r'\1', cleaned_text)  # Remove espaço antes de pontuação
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text, detected_style
    
    def _escape_xml(self, text: str) -> str:
        '''Escape XML special characters'''
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace('"', "&quot;")
                   .replace("'", "&apos;"))

    def _style_to_vts_emotion(self, style: str) -> str:
        '''
        Converte um estilo de voz para uma emoção do VTube Studio
        Retorna a emoção mapeada ou None se não houver mapeamento
        '''
        if not style:
            return None
        return self.STYLE_TO_VTS_EMOTION.get(style.lower(), None)
    
    async def _generate(self, content: str = None, **kwargs):
        '''Generate a output stream'''
        # Extrai estilo do texto se presente entre colchetes
        cleaned_content, detected_style = self._extract_style_from_text(content)
        
        # Usa o estilo detectado, ou o padrão da configuração, ou nenhum
        style_to_use = detected_style if detected_style else self.style
        
        # Converte estilo para emoção VTS
        vts_emotion = self._style_to_vts_emotion(style_to_use) if style_to_use else None
        
        # Build SSML if style or language is configured, otherwise use plain text
        if style_to_use or self.language:
            ssml_content = self._build_ssml(cleaned_content, style_to_use)
            result = self.speech_synthesizer.speak_ssml_async(ssml_content).get()
        else:
            result = self.speech_synthesizer.speak_text_async(cleaned_content).get()
        
        output_b = BytesIO(result.audio_data)
        
        with wave.open(output_b, "r") as f:
            sr = f.getframerate()
            sw = f.getsampwidth()
            ch = f.getnchannels()
            ab = f.readframes(f.getnframes())
        
        output = {
            "audio_bytes": ab,
            "sr": sr,
            "sw": sw,
            "ch": ch
        }
        
        # Adiciona emoção VTS se detectada (para integração com VTube Studio)
        if vts_emotion:
            output["emotion"] = vts_emotion
        
        yield output