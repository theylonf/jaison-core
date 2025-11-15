from enum import Enum
from typing import Dict, List, AsyncGenerator, Any
import logging

from .error import UnknownOpType, UnknownOpRole, UnknownOpID, DuplicateFilter, OperationUnloaded
from .base import Operation
from utils.helpers.singleton import Singleton
from utils.config import Config

class OpTypes(Enum):
    STT = "stt"
    T2T = "t2t"
    TTS = "tts"
    FILTER_AUDIO = "filter_audio"
    FILTER_TEXT = "filter_text"
    EMBEDDING = "embedding"
    VISION = "vision"
    
class OpRoles(Enum):
    STT = "stt"
    MCP = "mcp"
    T2T = "t2t"
    TTS = "tts"
    FILTER_AUDIO = "filter_audio"
    FILTER_TEXT = "filter_text"
    EMBEDDING = "embedding"
    VISION = "vision"
    
def role_to_type(op_role: OpRoles) -> OpTypes:
    match op_role:
        case OpRoles.STT:
            return OpTypes.STT
        case OpRoles.MCP:
            return OpTypes.T2T
        case OpRoles.T2T:
            return OpTypes.T2T
        case OpRoles.TTS:
            return OpTypes.TTS
        case OpRoles.FILTER_AUDIO:
            return OpTypes.FILTER_AUDIO
        case OpRoles.FILTER_TEXT:
            return OpTypes.FILTER_TEXT
        case OpRoles.EMBEDDING:
            return OpTypes.EMBEDDING
        case OpRoles.VISION:
            return OpTypes.VISION
        case _:
            raise UnknownOpRole(op_role)
    
    
def load_op(op_type: OpTypes, op_id: str):
    '''
    Return an operation, but do not saved to OperationManager
    
    Starting, usage and eventual closing of this operation is deferred to the caller.
    This is mainly used for temporarily loading an operation to be used, such
    as a filter used as a one-time preview and not intended to last whole session
    '''
    match op_type:
        case OpTypes.STT:
            if op_id == "fish":
                from .stt.fish import FishSTT
                return FishSTT()
            elif op_id == "azure":
                from .stt.azure import AzureSTT
                return AzureSTT()
            elif op_id == "openai":
                from .stt.openai import OpenAISTT
                return OpenAISTT()
            elif op_id == "kobold":
                from .stt.kobold import KoboldSTT
                return KoboldSTT()
            else:
                raise UnknownOpID("STT", op_id)
        case OpTypes.T2T:
            if op_id == "openai":
                from .t2t.openai import OpenAIT2T
                return OpenAIT2T()
            elif op_id == "kobold":
                from .t2t.kobold import KoboldT2T
                return KoboldT2T()
            elif op_id == "perplexity":
                from .t2t.perplexity import PerplexityT2T
                return PerplexityT2T()
            else:
                raise UnknownOpID("T2T", op_id)
        case OpTypes.TTS:
            if op_id == "azure":
                from .tts.azure import AzureTTS
                return AzureTTS()
            elif op_id == "fish":
                from .tts.fish import FishTTS
                return FishTTS()
            elif op_id == "openai":
                from .tts.openai import OpenAITTS
                return OpenAITTS()
            elif op_id == "kobold":
                from .tts.kobold import KoboldTTS
                return KoboldTTS()
            elif op_id == "melo":
                from .tts.melo import MeloTTS
                return MeloTTS()
            elif op_id == "pytts":
                from .tts.pytts import PyttsTTS
                return PyttsTTS()
            else:
                raise UnknownOpID("TTS", op_id)
        case OpTypes.FILTER_AUDIO:
            if op_id == "rvc":
                from .filter_audio.rvc import RVCFilter
                return RVCFilter()
            elif op_id == "pitch":
                from .filter_audio.pitch import PitchFilter
                return PitchFilter()
            else:
                raise UnknownOpID("FILTER_AUDIO", op_id)
        case OpTypes.FILTER_TEXT:
            if op_id == "chunker_sentence":
                from .filter_text.chunker_sentence import SentenceChunkerFilter
                return SentenceChunkerFilter()
            elif op_id == "emotion_roberta":
                from .filter_text.emotion_roberta import RobertaEmotionFilter
                return RobertaEmotionFilter()
            elif op_id == "mod_koala":
                from .filter_text.mod_koala import KoalaModerationFilter
                return KoalaModerationFilter()
            elif op_id == "filter_clean":
                from .filter_text.filter_clean import ResponseCleaningFilter
                return ResponseCleaningFilter()
            elif op_id == "style_preserver":
                from .filter_text.style_preserver import StylePreserverFilter
                return StylePreserverFilter()
            elif op_id == "vision_trigger":
                from .filter_text.vision_trigger import VisionTriggerFilter
                return VisionTriggerFilter()
            else:
                raise UnknownOpID("FILTER_TEXT", op_id)
        case OpTypes.EMBEDDING:
            if op_id == "openai":
                from .embedding.openai import OpenAIEmbedding
                return OpenAIEmbedding()
            else:
                raise UnknownOpID("EMBEDDING", op_id)
        case OpTypes.VISION:
            if op_id == "rapidapi_caption":
                from .vision.rapidapi_caption import RapidAPICaptionVision
                return RapidAPICaptionVision()
            elif op_id == "gemini_vision":
                from .vision.gemini_vision import GeminiVision
                return GeminiVision()
            else:
                raise UnknownOpID("VISION", op_id)
        case _:
            # Should never get here if op_role is indeed OpRole
            raise UnknownOpRole(op_type)
    
class OperationManager(metaclass=Singleton):
    def __init__(self):
        self.stt = None
        self.mcp = None
        self.mcp_fallback = list()  # Lista de operações mcp para fallback
        self.t2t = None
        self.t2t_fallback = list()  # Lista de operações t2t para fallback
        self.tts = None
        self.filter_audio = list()
        self.filter_text = list()
        self.embedding = None
        self.vision = None
        self.vision_fallback = list()  # Lista de operações vision para fallback
        
        # Blacklist temporária de APIs com rate limit (até reiniciar servidor)
        self.t2t_rate_limited = set()  # IDs de operações T2T com rate limit
        self.mcp_rate_limited = set()  # IDs de operações MCP com rate limit
        self.vision_rate_limited = set()  # IDs de operações Vision com rate limit

    def get_operation(self, op_role: OpRoles) -> Operation:
        match op_role:
            case OpRoles.STT:
                return self.stt
            case OpRoles.MCP:
                return self.mcp
            case OpRoles.T2T:
                return self.t2t
            case OpRoles.TTS:
                return self.tts
            case OpRoles.FILTER_AUDIO:
                return self.filter_audio
            case OpRoles.FILTER_TEXT:
                return self.filter_text
            case OpRoles.EMBEDDING:
                return self.embedding
            case OpRoles.VISION:
                return self.vision
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
            
    def get_operation_all(self) -> Dict[str, Operation | List[Operation]]:
        return {
            "stt": self.get_operation(OpRoles.STT),
            "mcp": self.get_operation(OpRoles.MCP),
            "t2t": self.get_operation(OpRoles.T2T),
            "tts": self.get_operation(OpRoles.TTS),
            "filter_audio": self.get_operation(OpRoles.FILTER_AUDIO),
            "filter_text": self.get_operation(OpRoles.FILTER_TEXT),
            "embedding": self.get_operation(OpRoles.EMBEDDING),
            "vision": self.get_operation(OpRoles.VISION),
        }
        
    async def get_configuration(
        self,
        op_role: OpRoles,
        op_id: str = None
    ):
        '''Get configuration for a loaded operation'''
        match op_role:
            case OpRoles.STT:
                if not self.stt:
                    raise OperationUnloaded("STT")
                elif op_id and self.stt and self.stt.op_id != op_id:
                    raise OperationUnloaded("STT", op_id=op_id)
                
                return await self.stt.get_configuration()
            case OpRoles.MCP:
                if not self.mcp:
                    raise OperationUnloaded("MCP")
                elif op_id and self.mcp and self.mcp.op_id != op_id:
                    raise OperationUnloaded("MCP", op_id=op_id)
                
                return await self.mcp.get_configuration()
            case OpRoles.T2T:
                if not self.t2t:
                    raise OperationUnloaded("T2T")
                elif op_id and self.t2t and self.t2t.op_id != op_id:
                    raise OperationUnloaded("T2T", op_id=op_id)
                
                return await self.t2t.get_configuration()
            case OpRoles.TTS:
                if not self.tts:
                    raise OperationUnloaded("TTS")
                elif op_id and self.tts and self.tts.op_id != op_id:
                    raise OperationUnloaded("TTS", op_id=op_id)
                
                return await self.tts.get_configuration()
            case OpRoles.FILTER_AUDIO:
                assert op_id is not None
                
                for op in self.filter_audio:
                    if op.op_id == op_id:
                        return await op.get_configuration()
                raise OperationUnloaded("FILTER_AUDIO", op_id=op_id)
            case OpRoles.FILTER_TEXT:
                assert op_id is not None
                
                for op in self.filter_text:
                    if op.op_id == op_id:
                        return await op.get_configuration()
                raise OperationUnloaded("FILTER_AUDIO", op_id=op_id)
            case OpRoles.EMBEDDING:
                if not self.embedding:
                    raise OperationUnloaded("EMBEDDING")
                elif op_id and self.embedding and self.embedding.op_id != op_id:
                    raise OperationUnloaded("EMBEDDING", op_id=op_id)
                
                return await self.embedding.get_configuration()
            case OpRoles.VISION:
                if not self.vision:
                    raise OperationUnloaded("VISION")
                elif op_id and self.vision and self.vision.op_id != op_id:
                    raise OperationUnloaded("VISION", op_id=op_id)
                
                return await self.vision.get_configuration()
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
        
    async def load_operation(self, op_role: OpRoles, op_id: str, op_details: Dict[str, Any]) -> None:
        '''Load, start, and save an Operation in the OperationManager'''
        if op_role == OpRoles.FILTER_AUDIO:
            for op in self.filter_audio:
                if op.op_id == op_id: raise DuplicateFilter("FILTER_AUDIO", op_id)
        if op_role == OpRoles.FILTER_TEXT:
            for op in self.filter_text:
                if op.op_id == op_id: raise DuplicateFilter("FILTER_TEXT", op_id)
                
        new_op = load_op(role_to_type(op_role), op_id)
        await new_op.configure(op_details)
        await new_op.start()
        
        match op_role:
            case OpRoles.STT:
                if self.stt: await self.stt.close()
                self.stt = new_op
            case OpRoles.MCP:
                # Se já existe uma operação mcp principal, move para fallback
                if self.mcp:
                    self.mcp_fallback.append(self.mcp)
                self.mcp = new_op
            case OpRoles.T2T:
                # Se já existe uma operação t2t principal, move para fallback
                if self.t2t:
                    self.t2t_fallback.append(self.t2t)
                self.t2t = new_op
            case OpRoles.TTS:
                if self.tts: await self.tts.close()
                self.tts = new_op
            case OpRoles.FILTER_AUDIO:
                self.filter_audio.append(new_op)
            case OpRoles.FILTER_TEXT:
                self.filter_text.append(new_op)
            case OpRoles.EMBEDDING:
                if self.embedding: await self.embedding.close()
                self.embedding = new_op
            case OpRoles.VISION:
                # Se já existe uma operação vision principal, move para fallback
                if self.vision:
                    self.vision_fallback.append(self.vision)
                self.vision = new_op
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
        
    async def load_operations_from_config(self) -> None:
        '''Load, start, and save all operations specified in config in the OperationManager'''
        config = Config()
        
        await self.close_operation_all()
        
        operations = Config().operations
        
        # Separar operações que suportam fallback (T2T, MCP e VISION) das outras
        t2t_ops = []
        mcp_ops = []
        vision_ops = []
        other_ops = []
        
        for op_details in operations:
            op_role = OpRoles(op_details['role'])
            if op_role == OpRoles.T2T:
                t2t_ops.append(op_details)
            elif op_role == OpRoles.MCP:
                mcp_ops.append(op_details)
            elif op_role == OpRoles.VISION:
                vision_ops.append(op_details)
            else:
                other_ops.append(op_details)
        
        # Processar T2T: encontrar principal ou usar primeira
        if t2t_ops:
            principal_t2t = None
            fallback_t2t = []
            
            # Procurar operação marcada como default
            for op_details in t2t_ops:
                if op_details.get('default', False):
                    principal_t2t = op_details
                    break
            
            # Se não encontrou default, primeira é default
            if principal_t2t is None and t2t_ops:
                principal_t2t = t2t_ops[0]
                fallback_t2t = t2t_ops[1:]
            else:
                # Adicionar outras como fallback na ordem que aparecem
                for op_details in t2t_ops:
                    if op_details != principal_t2t:
                        fallback_t2t.append(op_details)
            
            # Carregar default primeiro
            if principal_t2t:
                op_role = OpRoles(principal_t2t['role'])
                op_id = principal_t2t['id']
                await self.load_operation(op_role, op_id, principal_t2t)
            
            # Carregar fallbacks
            for op_details in fallback_t2t:
                op_role = OpRoles(op_details['role'])
                op_id = op_details['id']
                await self.load_operation(op_role, op_id, op_details)
        
        # Processar MCP: encontrar principal ou usar primeira
        if mcp_ops:
            principal_mcp = None
            fallback_mcp = []
            
            # Procurar operação marcada como default
            for op_details in mcp_ops:
                if op_details.get('default', False):
                    principal_mcp = op_details
                    break
            
            # Se não encontrou default, primeira é default
            if principal_mcp is None and mcp_ops:
                principal_mcp = mcp_ops[0]
                fallback_mcp = mcp_ops[1:]
            else:
                # Adicionar outras como fallback na ordem que aparecem
                for op_details in mcp_ops:
                    if op_details != principal_mcp:
                        fallback_mcp.append(op_details)
            
            # Carregar default primeiro
            if principal_mcp:
                op_role = OpRoles(principal_mcp['role'])
                op_id = principal_mcp['id']
                await self.load_operation(op_role, op_id, principal_mcp)
            
            # Carregar fallbacks
            for op_details in fallback_mcp:
                op_role = OpRoles(op_details['role'])
                op_id = op_details['id']
                await self.load_operation(op_role, op_id, op_details)
        
        # Processar VISION: encontrar principal ou usar primeira
        if vision_ops:
            principal_vision = None
            fallback_vision = []
            
            # Procurar operação marcada como default
            for op_details in vision_ops:
                if op_details.get('default', False):
                    principal_vision = op_details
                    break
            
            # Se não encontrou default, primeira é default
            if principal_vision is None and vision_ops:
                principal_vision = vision_ops[0]
                fallback_vision = vision_ops[1:]
            else:
                # Adicionar outras como fallback na ordem que aparecem
                for op_details in vision_ops:
                    if op_details != principal_vision:
                        fallback_vision.append(op_details)
            
            # Carregar default primeiro
            if principal_vision:
                op_role = OpRoles(principal_vision['role'])
                op_id = principal_vision['id']
                await self.load_operation(op_role, op_id, principal_vision)
            
            # Carregar fallbacks
            for op_details in fallback_vision:
                op_role = OpRoles(op_details['role'])
                op_id = op_details['id']
                await self.load_operation(op_role, op_id, op_details)
        
        # Carregar outras operações normalmente
        for op_details in other_ops:
            op_role = OpRoles(op_details['role'])
            op_id = op_details['id']
            await self.load_operation(op_role, op_id, op_details)
        
    async def close_operation(self, op_role: OpRoles, op_id: str = None) -> None:
        match op_role:
            case OpRoles.STT:
                if not self.stt:
                    raise OperationUnloaded("STT")
                elif op_id and self.stt and self.stt.op_id != op_id:
                    raise OperationUnloaded("STT", op_id=op_id)
                
                await self.stt.close()
                self.stt = None
            case OpRoles.T2T:
                if not self.mcp:
                    raise OperationUnloaded("MCP")
                elif op_id and self.mcp and self.mcp.op_id != op_id:
                    raise OperationUnloaded("MCP", op_id=op_id)
                
                await self.mcp.close()
                self.mcp = None
            case OpRoles.T2T:
                if not self.t2t:
                    raise OperationUnloaded("T2T")
                elif op_id and self.t2t and self.t2t.op_id != op_id:
                    raise OperationUnloaded("T2T", op_id=op_id)
                
                await self.t2t.close()
                self.t2t = None
            case OpRoles.TTS:
                if not self.tts:
                    raise OperationUnloaded("TTS")
                elif op_id and self.tts and self.tts.op_id != op_id:
                    raise OperationUnloaded("TTS", op_id=op_id)
                
                await self.tts.close()
                self.tts = None
            case OpRoles.FILTER_AUDIO:
                for op in self.filter_audio:
                    if op.op_id == op_id:
                        await op.close()
                        self.filter_audio.remove(op)
                        return
                raise OperationUnloaded("FILTER_AUDIO", op_id=op_id)
            case OpRoles.FILTER_TEXT:
                for op in self.filter_text:
                    if op.op_id == op_id:
                        await op.close()
                        self.filter_text.remove(op)
                        return
                raise OperationUnloaded("FILTER_TEXT", op_id=op_id)
            case OpRoles.EMBEDDING:
                if not self.embedding:
                    raise OperationUnloaded("EMBEDDING")
                elif op_id and self.embedding and self.embedding.op_id != op_id:
                    raise OperationUnloaded("EMBEDDING", op_id=op_id)
                
                await self.embedding.close()
                self.embedding = None
            case OpRoles.VISION:
                if not self.vision:
                    raise OperationUnloaded("VISION")
                elif op_id and self.vision and self.vision.op_id != op_id:
                    raise OperationUnloaded("VISION", op_id=op_id)
                
                await self.vision.close()
                self.vision = None
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
            
    async def close_operation_all(self):
        if self.stt:
            await self.stt.close()
            self.stt = None
        if self.mcp:
            await self.mcp.close()
            self.mcp = None
        for op in self.mcp_fallback:
            await op.close()
        self.mcp_fallback.clear()
        self.mcp_rate_limited.clear()
        if self.t2t:
            await self.t2t.close()
            self.t2t = None
        for op in self.t2t_fallback:
            await op.close()
        self.t2t_fallback.clear()
        self.t2t_rate_limited.clear()
        if self.tts:
            await self.tts.close()
            self.tts = None
        for op in self.filter_audio:
            await op.close()
        self.filter_audio.clear()
        for op in self.filter_text:
            await op.close()
        self.filter_text.clear()
        if self.embedding:
            await self.embedding.close()
            self.embedding = None
        if self.vision:
            await self.vision.close()
            self.vision = None
        for op in self.vision_fallback:
            await op.close()
        self.vision_fallback.clear()
        self.vision_rate_limited.clear()
        
    async def configure(self,
        op_role: OpRoles,
        config_d: Dict[str, Any],
        op_id: str = None
    ):
        '''Configure an operation that has already been loaded prior'''
        match op_role:
            case OpRoles.STT:
                if not self.stt:
                    raise OperationUnloaded("STT")
                elif op_id and self.stt and self.stt.op_id != op_id:
                    raise OperationUnloaded("STT", op_id=op_id)
                
                return await self.stt.configure(config_d)
            case OpRoles.MCP:
                if not self.mcp:
                    raise OperationUnloaded("MCP")
                elif op_id and self.mcp and self.mcp.op_id != op_id:
                    raise OperationUnloaded("MCP", op_id=op_id)
                
                return await self.mcp.configure(config_d)
            case OpRoles.T2T:
                if not self.t2t:
                    raise OperationUnloaded("T2T")
                elif op_id and self.t2t and self.t2t.op_id != op_id:
                    raise OperationUnloaded("T2T", op_id=op_id)
                
                return await self.t2t.configure(config_d)
            case OpRoles.TTS:
                if not self.tts:
                    raise OperationUnloaded("TTS")
                elif op_id and self.tts and self.tts.op_id != op_id:
                    raise OperationUnloaded("TTS", op_id=op_id)
                
                return await self.tts.configure(config_d)
            case OpRoles.FILTER_AUDIO:
                assert op_id is not None
                
                for op in self.filter_audio:
                    if op.op_id == op_id:
                        return await op.configure(config_d)
                raise OperationUnloaded("FILTER_AUDIO", op_id=op_id)
            case OpRoles.FILTER_TEXT:
                assert op_id is not None
                
                for op in self.filter_text:
                    if op.op_id == op_id:
                        return await op.configure(config_d)
                raise OperationUnloaded("FILTER_TEXT", op_id=op_id)
            case OpRoles.EMBEDDING:
                if not self.embedding:
                    raise OperationUnloaded("EMBEDDING")
                elif op_id and self.embedding and self.embedding.op_id != op_id:
                    raise OperationUnloaded("EMBEDDING", op_id=op_id)
                
                return await self.embedding.configure(config_d)
            case OpRoles.VISION:
                if not self.vision:
                    raise OperationUnloaded("VISION")
                elif op_id and self.vision and self.vision.op_id != op_id:
                    raise OperationUnloaded("VISION", op_id=op_id)
                
                return await self.vision.configure(config_d)
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
        
    async def _use_filter(self, filter_list: List[Operation], filter_idx: int, chunk_in: Dict[str, Any]):
        if filter_idx == len(filter_list): yield chunk_in
        elif filter_idx < len(filter_list)-1: # Not last filter
            async for result_chunk in filter_list[filter_idx](chunk_in):
                async for chunk_out in self._use_filter(filter_list, filter_idx+1, result_chunk):
                    yield chunk_out
        else: # Is last filter
            async for chunk_out in filter_list[filter_idx](chunk_in):
                yield chunk_out
    
    async def _use_t2t_with_fallback(self, chunk_in: Dict[str, Any], op_id: str = None):
        '''Tenta usar uma operação t2t e, se falhar com rate limit, tenta a próxima'''
        from openai import RateLimitError
        
        # Lista de todas as operações t2t disponíveis (principal + fallbacks)
        t2t_operations = []
        if self.t2t:
            t2t_operations.append(self.t2t)
        t2t_operations.extend(self.t2t_fallback)
        
        if not t2t_operations:
            raise OperationUnloaded("T2T")
        
        # Se op_id foi especificado, filtra apenas a operação correspondente
        if op_id:
            t2t_operations = [op for op in t2t_operations if op.op_id == op_id]
            if not t2t_operations:
                raise OperationUnloaded("T2T", op_id=op_id)
        
        # Filtrar operações que estão com rate limit (pular direto para fallback)
        available_operations = [op for op in t2t_operations if op.op_id not in self.t2t_rate_limited]
        
        # Se todas estão com rate limit, limpar blacklist e tentar novamente
        if not available_operations:
            logging.warning(f"[OperationManager] ⚠️ Todas as APIs T2T estão com rate limit, limpando blacklist e tentando novamente...")
            self.t2t_rate_limited.clear()
            available_operations = t2t_operations
        
        last_error = None
        tried_operations = []
        for idx, op in enumerate(available_operations):
            try:
                success = False
                async for chunk_out in op(chunk_in):
                    success = True
                    yield chunk_out
                # Se chegou aqui, a operação foi bem-sucedida
                if success:
                    if idx > 0:
                        # Se não era a primeira operação, houve fallback
                        logging.info(f"[OperationManager] ✅ T2T fallback bem-sucedido: {tried_operations[0]} → {op.op_id}")
                    return
            except RateLimitError as e:
                last_error = e
                tried_operations.append(op.op_id)
                # Adicionar à blacklist temporária
                self.t2t_rate_limited.add(op.op_id)
                logging.warning(f"[OperationManager] ⚠️ Rate limit atingido para T2T '{op.op_id}', adicionando à blacklist temporária")
                if idx < len(available_operations) - 1:
                    logging.warning(f"[OperationManager] ⚠️ Tentando fallback '{available_operations[idx+1].op_id}'...")
                else:
                    logging.warning(f"[OperationManager] ⚠️ Sem mais fallbacks disponíveis")
                continue
            except Exception as e:
                error_str = str(e).lower()
                
                # Erros que devem fazer fallback (temporários ou recuperáveis)
                should_fallback = False
                is_rate_limit = False
                
                # Rate limit (429)
                if "429" in str(e) or "rate limit" in error_str or "rate_limit" in error_str:
                    should_fallback = True
                    is_rate_limit = True
                # Erros de servidor (500, 502, 503, 504)
                elif any(code in str(e) for code in ["500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable", "gateway timeout"]):
                    should_fallback = True
                # Timeout errors
                elif "timeout" in error_str or "timed out" in error_str:
                    should_fallback = True
                # Connection errors
                elif any(term in error_str for term in ["connection", "network", "unreachable", "refused"]):
                    should_fallback = True
                
                if should_fallback:
                    last_error = e
                    tried_operations.append(op.op_id)
                    if is_rate_limit:
                        # Adicionar à blacklist temporária apenas para rate limit
                        self.t2t_rate_limited.add(op.op_id)
                        logging.warning(f"[OperationManager] ⚠️ Rate limit atingido para T2T '{op.op_id}', adicionando à blacklist temporária")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Erro temporário para T2T '{op.op_id}': {type(e).__name__}")
                    if idx < len(available_operations) - 1:
                        logging.warning(f"[OperationManager] ⚠️ Tentando fallback '{available_operations[idx+1].op_id}'...")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Sem mais fallbacks disponíveis")
                    continue
                else:
                    # Para erros definitivos (401, 400, etc.), propaga imediatamente
                    # Mas só se for a primeira operação, senão tenta fallback primeiro
                    if idx == 0 and len(available_operations) > 1:
                        # Se é a primeira e há fallback, tenta fallback mesmo para erros definitivos
                        last_error = e
                        tried_operations.append(op.op_id)
                        logging.warning(f"[OperationManager] ⚠️ Erro para T2T '{op.op_id}': {type(e).__name__}, tentando fallback...")
                        continue
                    else:
                        # Se não há fallback ou já tentou todos, propaga o erro
                        raise
        
        # Se todas as operações falharam com rate limit, levanta o último erro
        if last_error:
            raise last_error
        else:
            raise OperationUnloaded("T2T")
    
    async def _use_mcp_with_fallback(self, chunk_in: Dict[str, Any], op_id: str = None):
        '''Tenta usar uma operação mcp e, se falhar com rate limit, tenta a próxima'''
        from openai import RateLimitError
        
        # Lista de todas as operações mcp disponíveis (principal + fallbacks)
        mcp_operations = []
        if self.mcp:
            mcp_operations.append(self.mcp)
        mcp_operations.extend(self.mcp_fallback)
        
        if not mcp_operations:
            raise OperationUnloaded("MCP")
        
        # Se op_id foi especificado, filtra apenas a operação correspondente
        if op_id:
            mcp_operations = [op for op in mcp_operations if op.op_id == op_id]
            if not mcp_operations:
                raise OperationUnloaded("MCP", op_id=op_id)
        
        # Filtrar operações que estão com rate limit (pular direto para fallback)
        available_operations = [op for op in mcp_operations if op.op_id not in self.mcp_rate_limited]
        
        # Se todas estão com rate limit, limpar blacklist e tentar novamente
        if not available_operations:
            logging.warning(f"[OperationManager] ⚠️ Todas as APIs MCP estão com rate limit, limpando blacklist e tentando novamente...")
            self.mcp_rate_limited.clear()
            available_operations = mcp_operations
        
        last_error = None
        tried_operations = []
        for idx, op in enumerate(available_operations):
            try:
                success = False
                chunk_count = 0
                async for chunk_out in op(chunk_in):
                    success = True
                    chunk_count += 1
                    # Adicionar informação sobre qual API está sendo usada no chunk
                    chunk_out['_mcp_op_id'] = op.op_id
                    chunk_out['_mcp_op_idx'] = idx
                    yield chunk_out
                # Se chegou aqui, a operação foi bem-sucedida
                if success:
                    if idx > 0:
                        # Se não era a primeira operação, houve fallback
                        logging.info(f"[OperationManager] ✅ MCP fallback bem-sucedido: {tried_operations[0]} → {op.op_id}")
                        print(f"[MCP] ⚠️ Fallback detectado: {tried_operations[0]} → {op.op_id} ({chunk_count} chunks)")
                    return
            except RateLimitError as e:
                last_error = e
                tried_operations.append(op.op_id)
                # Adicionar à blacklist temporária
                self.mcp_rate_limited.add(op.op_id)
                logging.warning(f"[OperationManager] ⚠️ Rate limit atingido para MCP '{op.op_id}', adicionando à blacklist temporária")
                if idx < len(available_operations) - 1:
                    logging.warning(f"[OperationManager] ⚠️ Tentando fallback '{available_operations[idx+1].op_id}'...")
                else:
                    logging.warning(f"[OperationManager] ⚠️ Sem mais fallbacks disponíveis")
                continue
            except Exception as e:
                error_str = str(e).lower()
                
                # Erros que devem fazer fallback (temporários ou recuperáveis)
                should_fallback = False
                is_rate_limit = False
                
                # Rate limit (429)
                if "429" in str(e) or "rate limit" in error_str or "rate_limit" in error_str:
                    should_fallback = True
                    is_rate_limit = True
                # Erros de servidor (500, 502, 503, 504)
                elif any(code in str(e) for code in ["500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable", "gateway timeout"]):
                    should_fallback = True
                # Timeout errors
                elif "timeout" in error_str or "timed out" in error_str:
                    should_fallback = True
                # Connection errors
                elif any(term in error_str for term in ["connection", "network", "unreachable", "refused"]):
                    should_fallback = True
                
                if should_fallback:
                    last_error = e
                    tried_operations.append(op.op_id)
                    if is_rate_limit:
                        # Adicionar à blacklist temporária apenas para rate limit
                        self.mcp_rate_limited.add(op.op_id)
                        logging.warning(f"[OperationManager] ⚠️ Rate limit atingido para MCP '{op.op_id}', adicionando à blacklist temporária")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Erro temporário para MCP '{op.op_id}': {type(e).__name__}")
                    if idx < len(available_operations) - 1:
                        logging.warning(f"[OperationManager] ⚠️ Tentando fallback '{available_operations[idx+1].op_id}'...")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Sem mais fallbacks disponíveis")
                    continue
                else:
                    # Para erros definitivos (401, 400, etc.), propaga imediatamente
                    # Mas só se for a primeira operação, senão tenta fallback primeiro
                    if idx == 0 and len(available_operations) > 1:
                        # Se é a primeira e há fallback, tenta fallback mesmo para erros definitivos
                        last_error = e
                        tried_operations.append(op.op_id)
                        logging.warning(f"[OperationManager] ⚠️ Erro para MCP '{op.op_id}': {type(e).__name__}, tentando fallback...")
                        continue
                    else:
                        # Se não há fallback ou já tentou todos, propaga o erro
                        raise
        
        # Se todas as operações falharam com rate limit, levanta o último erro
        if last_error:
            raise last_error
        else:
            raise OperationUnloaded("MCP")
    
    async def _use_vision_with_fallback(self, chunk_in: Dict[str, Any], op_id: str = None):
        '''Tenta usar uma operação vision e, se falhar, tenta a próxima'''
        # Lista de todas as operações vision disponíveis (principal + fallbacks)
        vision_operations = []
        if self.vision:
            vision_operations.append(self.vision)
        vision_operations.extend(self.vision_fallback)
        
        if not vision_operations:
            raise OperationUnloaded("VISION")
        
        # Se op_id foi especificado, filtra apenas a operação correspondente
        if op_id:
            vision_operations = [op for op in vision_operations if op.op_id == op_id]
            if not vision_operations:
                raise OperationUnloaded("VISION", op_id=op_id)
        
        # Filtrar operações que estão com rate limit (pular direto para fallback)
        available_operations = [op for op in vision_operations if op.op_id not in self.vision_rate_limited]
        
        # Se todas estão com rate limit, limpar blacklist e tentar novamente
        if not available_operations:
            logging.warning(f"[OperationManager] ⚠️ Todas as APIs Vision estão com rate limit, limpando blacklist e tentando novamente...")
            self.vision_rate_limited.clear()
            available_operations = vision_operations
        
        last_error = None
        tried_operations = []
        image_sent = False  # Flag para controlar se a imagem já foi enviada
        
        for idx, op in enumerate(available_operations):
            try:
                success = False
                async for chunk_out in op(chunk_in):
                    success = True
                    
                    # Adicionar informação sobre qual API está sendo usada
                    chunk_out['_vision_op_id'] = op.op_id
                    chunk_out['_vision_op_idx'] = idx
                    
                    # Se já enviamos a imagem e este chunk também tem imagem, pular o envio da imagem
                    # (evitar duplicação durante fallback)
                    if image_sent and chunk_out.get('image_bytes') and chunk_out.get('processing', False):
                        # Já enviamos a imagem, não enviar novamente
                        print(f"[Vision] ⚠️ Imagem já enviada, pulando envio duplicado da API {op.op_id}")
                        # Mas ainda precisamos processar o chunk para obter a descrição
                        # Remover image_bytes deste chunk para evitar duplicação
                        chunk_out_no_image = chunk_out.copy()
                        chunk_out_no_image.pop('image_bytes', None)
                        # Se não há mais nada útil no chunk, pular
                        if chunk_out_no_image.get('description') is None and not chunk_out_no_image.get('error'):
                            continue
                        yield chunk_out_no_image
                    else:
                        # Primeira vez ou chunk final com descrição
                        if chunk_out.get('image_bytes') and chunk_out.get('processing', False):
                            image_sent = True  # Marcar que imagem foi enviada
                            print(f"[Vision] 📤 Enviando imagem da API {op.op_id}...")
                        yield chunk_out
                
                # Se chegou aqui, a operação foi bem-sucedida
                if success:
                    if idx > 0:
                        # Se não era a primeira operação, houve fallback
                        print(f"[Vision] ✅ Fallback bem-sucedido: {tried_operations[0]} → {op.op_id}")
                        logging.info(f"[OperationManager] ✅ Vision fallback bem-sucedido: {tried_operations[0]} → {op.op_id}")
                    return
            except Exception as e:
                error_str = str(e).lower()
                
                # Erros que devem fazer fallback (temporários, recuperáveis ou de autenticação)
                should_fallback = False
                is_rate_limit = False
                is_auth_error = False
                
                # Rate limit (429)
                if "429" in str(e) or "rate limit" in error_str or "rate_limit" in error_str:
                    should_fallback = True
                    is_rate_limit = True
                # Erros de autenticação/autorização (401, 403) - fallback pode ter outra chave
                elif any(code in str(e) for code in ["401", "403", "unauthorized", "forbidden"]):
                    should_fallback = True
                    is_auth_error = True
                # Erros de servidor (500, 502, 503, 504)
                elif any(code in str(e) for code in ["500", "502", "503", "504", "internal server error", "bad gateway", "service unavailable", "gateway timeout"]):
                    should_fallback = True
                # Timeout errors (408, 504)
                elif "408" in str(e) or "timeout" in error_str or "timed out" in error_str:
                    should_fallback = True
                # Connection errors
                elif any(term in error_str for term in ["connection", "network", "unreachable", "refused"]):
                    should_fallback = True
                
                if should_fallback:
                    last_error = e
                    tried_operations.append(op.op_id)
                    if is_rate_limit or is_auth_error:
                        # Adicionar à blacklist temporária para rate limit e erros de autenticação
                        self.vision_rate_limited.add(op.op_id)
                        if is_rate_limit:
                            logging.warning(f"[OperationManager] ⚠️ Rate limit atingido para Vision '{op.op_id}', adicionando à blacklist temporária")
                        else:
                            logging.warning(f"[OperationManager] ⚠️ Erro de autenticação/autorização para Vision '{op.op_id}', adicionando à blacklist temporária")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Erro temporário para Vision '{op.op_id}': {type(e).__name__}")
                    if idx < len(available_operations) - 1:
                        logging.warning(f"[OperationManager] ⚠️ Tentando fallback '{available_operations[idx+1].op_id}'...")
                    else:
                        logging.warning(f"[OperationManager] ⚠️ Sem mais fallbacks disponíveis")
                    continue
                else:
                    # Para outros erros (400, 404, etc.), tenta fallback se houver
                    # Mas só se for a primeira operação, senão propaga
                    if idx == 0 and len(available_operations) > 1:
                        # Se é a primeira e há fallback, tenta fallback mesmo para erros definitivos
                        last_error = e
                        tried_operations.append(op.op_id)
                        logging.warning(f"[OperationManager] ⚠️ Erro para Vision '{op.op_id}': {type(e).__name__}, tentando fallback...")
                        continue
                    else:
                        # Se não há fallback ou já tentou todos, propaga o erro
                        raise
        
        # Se todas as operações falharam, levanta o último erro
        if last_error:
            raise last_error
        else:
            raise OperationUnloaded("VISION")
            
    def use_operation(
        self,
        op_role: OpRoles,
        chunk_in: Dict[str, Any],
        op_id: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        '''Use an operation that has already been loaded prior'''
        match op_role:
            case OpRoles.STT:
                if not self.stt:
                    raise OperationUnloaded("STT")
                elif op_id and self.stt and self.stt.op_id != op_id:
                    raise OperationUnloaded("STT", op_id=op_id)
                
                return self.stt(chunk_in)
            case OpRoles.MCP:
                return self._use_mcp_with_fallback(chunk_in, op_id)
            case OpRoles.T2T:
                return self._use_t2t_with_fallback(chunk_in, op_id)
            case OpRoles.TTS:
                if not self.tts:
                    raise OperationUnloaded("TTS")
                elif op_id and self.tts and self.tts.op_id != op_id:
                    raise OperationUnloaded("TTS", op_id=op_id)
                
                return self.tts(chunk_in)
            case OpRoles.FILTER_AUDIO:
                if op_id:
                    for op in self.filter_audio:
                        if op.op_id == op_id:
                            return op(chunk_in)
                    raise OperationUnloaded("FILTER_AUDIO", op_id=op_id)
                else:
                    return self._use_filter(self.filter_audio, 0, chunk_in)
            case OpRoles.FILTER_TEXT:
                if op_id:
                    for op in self.filter_text:
                        if op.op_id == op_id:
                            return op(chunk_in)
                    raise OperationUnloaded("FILTER_TEXT", op_id=op_id)
                else:
                    return self._use_filter(self.filter_text, 0, chunk_in)
            case OpRoles.EMBEDDING:
                if not self.embedding:
                    raise OperationUnloaded("EMBEDDING")
                elif op_id and self.embedding and self.embedding.op_id != op_id:
                    raise OperationUnloaded("EMBEDDING", op_id=op_id)
                
                return self.embedding(chunk_in)
            case OpRoles.VISION:
                return self._use_vision_with_fallback(chunk_in, op_id)
            case _:
                # Should never get here if op_role is indeed OpRoles
                raise UnknownOpRole(op_role)
