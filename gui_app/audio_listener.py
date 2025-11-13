import json
import asyncio
import websockets
from PySide6 import QtCore


class AudioListener(QtCore.QThread):
    audio_received = QtCore.Signal(bytes, int, int, int)  # audio_bytes, sr, sw, ch
    audio_chunk_received = QtCore.Signal(str, int, int, int)  # audio_b64_chunk, sr, sw, ch
    audio_complete = QtCore.Signal(int, int, int)  # sr, sw, ch - signal when all chunks received
    text_received = QtCore.Signal(str, str)  # text, user_name
    image_received = QtCore.Signal(str, str, str, str)  # image_bytes_b64, user_name, image_format, error
    error_received = QtCore.Signal(str)  # error message

    def __init__(self, ws_url: str):
        super().__init__()
        self.ws_url = ws_url
        self._stop = False
        self.current_audio_sr = 16000
        self.current_audio_sw = 2
        self.current_audio_ch = 1

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._listen())
        except Exception as e:
            pass  # Error already logged
            import traceback
            traceback.print_exc()
        finally:
            pass

    async def _listen(self):
        while not self._stop:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    while not self._stop:
                        try:
                            data = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            message = json.loads(data)
                            
                            # Handle response format from server
                            # Format: {"status": 200, "message": "event_id", "response": {...}}
                            if isinstance(message, list) and len(message) > 0:
                                message = message[0]
                            
                            event_type = message.get("message", "")
                            response = message.get("response", {})
                            status_code = message.get("status", 200)
                            
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
                                self.audio_chunk_received.emit(audio_b64, sr, sw, ch)
                            
                            # Check for vision screenshot event
                            # The event_type is inside result, not directly in response
                            if isinstance(result, dict) and result.get("event_type") == "vision_screenshot":
                                image_bytes_b64 = result.get("image_bytes")
                                image_format = result.get("image_format", "png")
                                user_name = result.get("user", "Sistema")
                                error = result.get("error")
                                # Emit signal with all parameters (including error)
                                self.image_received.emit(
                                    image_bytes_b64 or "",
                                    user_name,
                                    image_format,
                                    error or ""
                                )
                            
                            # Check for text content in result
                            if isinstance(result, dict):
                                # Check for content in result
                                content = result.get("content", "")
                                user_name = result.get("user", "")  # Get user name from result
                                if content and content.strip():
                                    self.text_received.emit(content, user_name)
                                # Also check raw_content
                                raw_content = result.get("raw_content", "")
                                if raw_content and raw_content.strip() and not content:
                                    self.text_received.emit(raw_content, user_name)
                            
                            # Check for content directly in response (alternative format)
                            if "content" in response and not isinstance(response["content"], dict):
                                content = response["content"]
                                user_name = response.get("user", "")
                                if content and content.strip():
                                    self.text_received.emit(content, user_name)
                            
                            # Check for raw_content directly in response
                            if "raw_content" in response:
                                raw_content = response["raw_content"]
                                user_name = response.get("user", "")
                                if raw_content and raw_content.strip():
                                    self.text_received.emit(raw_content, user_name)
                            
                            # Check for errors in response
                            if response.get("success") == False or response.get("error"):
                                error_info = response.get("error", {})
                                if isinstance(error_info, dict):
                                    error_msg = error_info.get("message", str(error_info))
                                else:
                                    error_msg = str(error_info)
                                self.error_received.emit(error_msg)
                            
                            # Check for job completion (success event) - signal to assemble audio
                            # The server sends events with finished=True when job completes
                            finished = response.get("finished", False)
                            success = response.get("success", False)
                            job_id = response.get("job_id", "")
                            
                            # Check for completion: event_type == "response" with finished=True
                            if event_type == "response" and finished:
                                # Only emit audio_complete if successful
                                if success is not False:
                                    self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                            
                            # Also check for "response_success" event type (legacy)
                            elif event_type == "response_success":
                                self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                            
                            # Also check if response indicates completion in other ways
                            elif response.get("status") == "completed" or response.get("complete", False):
                                self.audio_complete.emit(self.current_audio_sr, self.current_audio_sw, self.current_audio_ch)
                            
                            # Check for error status codes
                            status_code = message.get("status", 200)
                            if status_code >= 400:
                                error_msg = f"Erro HTTP {status_code}: {response.get('error', 'Erro desconhecido')}"
                                self.error_received.emit(error_msg)
                        except asyncio.TimeoutError:
                            # Timeout é normal, apenas continua aguardando
                            continue
                        except websockets.exceptions.ConnectionClosed as e:
                            break
                        except json.JSONDecodeError as e:
                            continue
            except websockets.exceptions.InvalidURI as e:
                if not self._stop:
                    await asyncio.sleep(5)
            except websockets.exceptions.InvalidHandshake as e:
                if not self._stop:
                    await asyncio.sleep(5)
            except Exception as e:
                if not self._stop:
                    await asyncio.sleep(2)
                else:
                    break

    def stop(self) -> None:
        self._stop = True

