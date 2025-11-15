from openai import AsyncOpenAI
import os

from .base import T2TOperation
from utils.prompter.message import ChatMessage
from utils.prompter import Prompter

class PerplexityT2T(T2TOperation):
    def __init__(self):
        super().__init__("perplexity")
        self.client = None
        
        self.base_url = "https://api.perplexity.ai"
        self.model = "sonar-pro"
        self.temperature = 1
        self.top_p = 0.9
        self.presence_penalty = 0
        self.frequency_penalty = 0
        self.api_key = None
        
    async def start(self):
        await super().start()
        # Perplexity usa o mesmo formato OpenAI, mas precisa da API key
        api_key = self.api_key or os.environ.get("PERPLEXITY_API_KEY")
        if not api_key:
            raise ValueError("PERPLEXITY_API_KEY não encontrada. Configure via variável de ambiente ou no config.")
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=api_key)
        
    async def close(self):
        await super().close()
        if self.client:
            await self.client.close()
        self.client = None
        
    async def configure(self, config_d):
        '''Configure and validate operation-specific configuration'''
        if "base_url" in config_d: self.base_url = str(config_d['base_url'])
        if "model" in config_d: self.model = str(config_d['model'])
        if "api_key" in config_d: self.api_key = str(config_d['api_key'])

        if "temperature" in config_d: self.temperature = float(config_d['temperature'])
        if "top_p" in config_d: self.top_p = float(config_d['top_p'])
        if "presence_penalty" in config_d: self.presence_penalty = float(config_d['presence_penalty'])
        if "frequency_penalty" in config_d: self.frequency_penalty = float(config_d['frequency_penalty'])
        
        assert self.base_url is not None and len(self.base_url) > 0
        assert self.model is not None and len(self.model) > 0
        assert self.temperature >= 0 and self.temperature <= 2
        assert self.top_p >= 0 and self.top_p <= 1
        assert self.presence_penalty >= 0 and self.presence_penalty <= 1
        assert self.frequency_penalty >= 0 and self.frequency_penalty <= 1
        
    async def get_configuration(self):
        '''Returns values of configurable fields'''
        return {
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
        }

    async def _generate(self, instruction_prompt: str = None, messages: list = None, **kwargs):
        # Perplexity requer que mensagens alternem entre user e assistant após system
        history = []
        
        # Adicionar system message se fornecido
        if instruction_prompt and instruction_prompt.strip():
            history.append({ "role": "system", "content": instruction_prompt.strip() })
        
        # Processar mensagens e garantir alternância correta
        # Combinar mensagens consecutivas do mesmo tipo
        last_role = None
        last_content = None
        
        for msg in messages:
            if msg is None:
                continue
            
            current_role = None
            content = None
            
            if isinstance(msg, ChatMessage) and msg.user == Prompter().character_name:
                # Mensagem do assistente
                content = msg.message
                if content and content.strip():
                    current_role = "assistant"
            else:
                # Mensagem do usuário (ou outro tipo)
                if hasattr(msg, 'to_line'):
                    content = msg.to_line()
                else:
                    content = str(msg)
                if content and content.strip():
                    current_role = "user"
            
            if current_role and content:
                content = content.strip()
                
                # Se é o mesmo tipo da última mensagem, combinar
                if last_role == current_role and last_content:
                    # Combinar conteúdo
                    last_content = f"{last_content}\n{content}"
                else:
                    # Adicionar a mensagem anterior se houver
                    if last_role and last_content:
                        history.append({ "role": last_role, "content": last_content })
                    # Começar nova mensagem
                    last_role = current_role
                    last_content = content
        
        # Adicionar a última mensagem processada
        if last_role and last_content:
            history.append({ "role": last_role, "content": last_content })
        
        # Garantir que há pelo menos uma mensagem user após system
        if len(history) == 0 or (len(history) == 1 and history[0]["role"] == "system"):
            raise ValueError("Perplexity requer pelo menos uma mensagem de usuário após a mensagem do sistema")
        
        # Garantir que após system, a primeira mensagem seja user
        if len(history) > 1 and history[0]["role"] == "system":
            # Se a primeira mensagem após system não é user, adicionar uma mensagem user vazia
            if history[1]["role"] != "user":
                history.insert(1, { "role": "user", "content": "" })
        
        # Verificar e corrigir alternância
        if len(history) > 1:
            start_idx = 1 if history[0]["role"] == "system" else 0
            expected_role = "user"
            
            # Reconstruir history garantindo alternância correta
            corrected_history = []
            if start_idx == 1:
                corrected_history.append(history[0])  # system
            
            for i in range(start_idx, len(history)):
                if history[i]["role"] == expected_role:
                    corrected_history.append(history[i])
                    expected_role = "assistant" if expected_role == "user" else "user"
                elif history[i]["role"] == "assistant" and expected_role == "user":
                    # Se esperamos user mas temos assistant, adicionar user vazio primeiro
                    corrected_history.append({ "role": "user", "content": "" })
                    corrected_history.append(history[i])
                    expected_role = "user"  # Próxima deve ser user
            
            history = corrected_history

        stream = await self.client.chat.completions.create(
            messages=history,
            model=self.model,
            stream=True,
            temperature=self.temperature,
            top_p=self.top_p,
            presence_penalty=self.presence_penalty,
            frequency_penalty=self.frequency_penalty
        )

        full_response = ""
        async for chunk in stream:
            content_chunk = chunk.choices[0].delta.content or ""
            full_response += content_chunk
            yield {"content": content_chunk}

