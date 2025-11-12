import json
import asyncio
import websockets
from PySide6 import QtCore


class AudioListener(QtCore.QThread):
    audio_received = QtCore.Signal(bytes, int, int, int)  # audio_bytes, sr, sw, ch
    audio_chunk_received = QtCore.Signal(str, int, int, int)  # audio_b64_chunk, sr, sw, ch
    audio_complete = QtCore.Signal(int, int, int)  # sr, sw, ch - signal when all chunks received
    text_received = QtCore.Signal(str)
    error_received = QtCore.Signal(str)  # error message

    def __init__(self, ws_url: str):
        super().__init__()
        self.ws_url = ws_url
        self._stop = False
        self.current_audio_sr = 16000
        self.current_audio_sw = 2
        self.current_audio_ch = 1

    def run(self) -> None:
        print(f"[WebSocket] Thread iniciada, criando event loop...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        print(f"[WebSocket] Event loop criado, iniciando _listen()...")
        try:
            loop.run_until_complete(self._listen())
        except Exception as e:
            print(f"[WebSocket] ❌ Erro no event loop: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"[WebSocket] Thread finalizada")

    async def _listen(self):
        while not self._stop:
            try:
                print(f"[WebSocket] 🔌 Tentando conectar em {self.ws_url}...")
                async with websockets.connect(self.ws_url) as ws:
                    print(f"[WebSocket] ✅ Conectado! Aguardando eventos...")
                    while not self._stop:
                        try:
                            data = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            message = json.loads(data)
                            
                            # Debug: log raw message
                            print(f"[WebSocket] 📨 Mensagem recebida: {json.dumps(message, indent=2, ensure_ascii=False)[:500]}")
                            
                            # Handle response format from server
                            # Format: {"status": 200, "message": "event_id", "response": {...}}
                            if isinstance(message, list) and len(message) > 0:
                                message = message[0]
                            
                            event_type = message.get("message", "")
                            response = message.get("response", {})
                            status_code = message.get("status", 200)
                            
                            # Debug: log event type and structure
                            print(f"[WebSocket] 🔍 Evento tipo: '{event_type}', Status: {status_code}")
                            print(f"[WebSocket] 🔍 Response keys: {list(response.keys())}")
                            if "result" in response:
                                result = response.get("result", {})
                                if isinstance(result, dict):
                                    print(f"[WebSocket] 🔍 Result keys: {list(result.keys())}")
                            
                            # Get result from response (audio and text are usually in result)
                            result = response.get("result", {})
                            if not isinstance(result, dict):
                                result = {}
                            
                            # Check for audio data in result (primary location)
                            if "audio_bytes" in result:
                                audio_b64 = result.get("audio_bytes", "")
                                sr = result.get("sr", 16000)
                                sw = result.get("sw", 2)
                                ch = result.get("ch", 1)
                                
                                # Store audio parameters
                                self.current_audio_sr = sr
                                self.current_audio_sw = sw
                                self.current_audio_ch = ch
                                
                                # Emit chunk signal for reassembly
                                print(f"[WebSocket] Chunk de áudio detectado em result (sr={sr}, ch={ch}, tamanho_b64={len(audio_b64)})")
                                self.audio_chunk_received.emit(audio_b64, sr, sw, ch)
                            
                            # Check for audio data directly in response (fallback)
                            elif "audio_bytes" in response:
                                audio_b64 = response.get("audio_bytes", "")
                                sr = response.get("sr", 16000)
                                sw = response.get("sw", 2)
                                ch = response.get("ch", 1)
                                
                                # Store audio parameters
                                self.current_audio_sr = sr
                                self.current_audio_sw = sw
                                self.current_audio_ch = ch
                                
                                # Emit chunk signal for reassembly
                                print(f"[WebSocket] Chunk de áudio detectado em response (sr={sr}, ch={ch}, tamanho_b64={len(audio_b64)})")
                                self.audio_chunk_received.emit(audio_b64, sr, sw, ch)
                            
                            # Check for text content in result
                            if isinstance(result, dict):
                                # Check for content in result
                                content = result.get("content", "")
                                if content and content.strip():
                                    print(f"[WebSocket] Texto detectado em result.content: {content[:100]}...")
                                    self.text_received.emit(content)
                                # Also check raw_content
                                raw_content = result.get("raw_content", "")
                                if raw_content and raw_content.strip() and not content:
                                    print(f"[WebSocket] Texto detectado em result.raw_content: {raw_content[:100]}...")
                                    self.text_received.emit(raw_content)
                            
                            # Check for content directly in response (alternative format)
                            if "content" in response and not isinstance(response["content"], dict):
                                content = response["content"]
                                if content and content.strip():
                                    print(f"[WebSocket] Texto detectado em response.content: {content[:100]}...")
                                    self.text_received.emit(content)
                            
                            # Check for raw_content directly in response
                            if "raw_content" in response:
                                raw_content = response["raw_content"]
                                if raw_content and raw_content.strip():
                                    print(f"[WebSocket] Texto detectado em response.raw_content: {raw_content[:100]}...")
                                    self.text_received.emit(raw_content)
                            
                            # Check for errors in response
                            if response.get("success") == False or response.get("error"):
                                error_info = response.get("error", {})
                                if isinstance(error_info, dict):
                                    error_msg = error_info.get("message", str(error_info))
                                else:
                                    error_msg = str(error_info)
                                print(f"[WebSocket] ❌ Erro detectado: {error_msg}")
                                self.error_received.emit(error_msg)
                            
                            # Check for job completion (success event) - signal to assemble audio
                            # The server sends events with finished=True when job completes
                            finished = response.get("finished", False)
                            success = response.get("success", False)
                            job_id = response.get("job_id", "")
                            
                            print(f"[WebSocket] 🔍 Verificando conclusão: event_type='{event_type}', finished={finished}, success={success}, job_id={job_id}")
                            
                            # Check for completion: event_type == "response" with finished=True
                            if event_type == "response" and finished:
                                print(f"[WebSocket] ✅ Evento de conclusão detectado: {event_type}, finished={finished}, success={success}")
                                print(f"[WebSocket] Parâmetros de áudio armazenados: sr={self.current_audio_sr}, sw={self.current_audio_sw}, ch={self.current_audio_ch}")
                                # Only emit audio_complete if successful
                                if success is not False:
                                    print(f"[WebSocket] ✅ Emitindo sinal audio_complete")
                                    self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                                else:
                                    print(f"[WebSocket] ⚠️ Job concluído mas success=False, não emitindo audio_complete")
                            
                            # Also check for "response_success" event type (legacy)
                            elif event_type == "response_success":
                                print(f"[WebSocket] ✅ Evento response_success detectado (legacy)")
                                self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                            
                            # Also check if response indicates completion in other ways
                            elif response.get("status") == "completed" or response.get("complete", False):
                                print(f"[WebSocket] ✅ Status de conclusão detectado no response (status/complete)")
                                self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                            
                            # Check for error status codes
                            status_code = message.get("status", 200)
                            if status_code >= 400:
                                error_msg = f"Erro HTTP {status_code}: {response.get('error', 'Erro desconhecido')}"
                                print(f"[WebSocket] ❌ {error_msg}")
                                self.error_received.emit(error_msg)
                        except asyncio.TimeoutError:
                            # Timeout é normal, apenas continua aguardando
                            continue
                        except websockets.exceptions.ConnectionClosed as e:
                            print(f"[WebSocket] ⚠️ Conexão fechada: {e}")
                            break
                        except json.JSONDecodeError as e:
                            print(f"[WebSocket] ❌ Erro ao decodificar JSON: {e}")
                            print(f"[WebSocket] Dados recebidos: {data[:200] if 'data' in locals() else 'N/A'}")
                            continue
            except websockets.exceptions.InvalidURI as e:
                print(f"[WebSocket] ❌ URI inválida: {e}")
                if not self._stop:
                    await asyncio.sleep(5)
            except websockets.exceptions.InvalidHandshake as e:
                print(f"[WebSocket] ❌ Handshake inválido: {e}")
                if not self._stop:
                    await asyncio.sleep(5)
            except Exception as e:
                if not self._stop:
                    print(f"[WebSocket] ❌ Erro no websocket: {e}")
                    import traceback
                    traceback.print_exc()
                    await asyncio.sleep(2)
                else:
                    break

    def stop(self) -> None:
        self._stop = True

