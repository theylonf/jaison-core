"""
Script de teste para verificar se o WebSocket está recebendo eventos corretamente.
Execute este script para testar a conexão WebSocket e ver todos os eventos recebidos.
"""
import asyncio
import json
import websockets
import sys


async def test_websocket(host="127.0.0.1", port=7272):
    """Test WebSocket connection and log all received events."""
    ws_url = f"ws://{host}:{port}/"
    print(f"Conectando ao WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ Conectado ao WebSocket!")
            print("Aguardando eventos... (pressione Ctrl+C para sair)\n")
            
            event_count = 0
            while True:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    event_count += 1
                    
                    try:
                        message = json.loads(data)
                        
                        # Handle list format
                        if isinstance(message, list) and len(message) > 0:
                            message = message[0]
                        
                        event_type = message.get("message", "")
                        response = message.get("response", {})
                        status = message.get("status", "")
                        
                        print(f"\n{'='*60}")
                        print(f"Evento #{event_count}")
                        print(f"{'='*60}")
                        print(f"Tipo de evento: {event_type}")
                        print(f"Status: {status}")
                        print(f"Response keys: {list(response.keys())}")
                        
                        # Check for audio in result first (primary location)
                        result = response.get("result", {})
                        if isinstance(result, dict) and "audio_bytes" in result:
                            audio_b64 = result.get("audio_bytes", "")
                            sr = result.get("sr", "N/A")
                            sw = result.get("sw", "N/A")
                            ch = result.get("ch", "N/A")
                            print(f"🎵 ÁUDIO DETECTADO em result!")
                            print(f"  - Tamanho base64: {len(audio_b64)} caracteres")
                            print(f"  - Sample rate: {sr}")
                            print(f"  - Sample width: {sw}")
                            print(f"  - Channels: {ch}")
                        # Check for audio directly in response (fallback)
                        elif "audio_bytes" in response:
                            audio_b64 = response.get("audio_bytes", "")
                            sr = response.get("sr", "N/A")
                            sw = response.get("sw", "N/A")
                            ch = response.get("ch", "N/A")
                            print(f"🎵 ÁUDIO DETECTADO em response!")
                            print(f"  - Tamanho base64: {len(audio_b64)} caracteres")
                            print(f"  - Sample rate: {sr}")
                            print(f"  - Sample width: {sw}")
                            print(f"  - Channels: {ch}")
                        
                        # Check for text
                        if "result" in response:
                            result = response["result"]
                            if isinstance(result, dict):
                                content = result.get("content", "")
                                raw_content = result.get("raw_content", "")
                                if content:
                                    print(f"📝 TEXTO (content): {content[:200]}...")
                                if raw_content:
                                    print(f"📝 TEXTO (raw_content): {raw_content[:200]}...")
                        
                        if "content" in response and not isinstance(response["content"], dict):
                            content = response["content"]
                            if content:
                                print(f"📝 TEXTO (direct): {content[:200]}...")
                        
                        if "raw_content" in response:
                            raw_content = response["raw_content"]
                            if raw_content:
                                print(f"📝 TEXTO (raw_content direct): {raw_content[:200]}...")
                        
                        # Check for completion indicators
                        finished = response.get("finished", False)
                        complete = response.get("complete", False)
                        status_completed = response.get("status") == "completed"
                        
                        if finished or complete or status_completed:
                            print(f"✅ INDICADOR DE CONCLUSÃO:")
                            print(f"  - finished: {finished}")
                            print(f"  - complete: {complete}")
                            print(f"  - status: {response.get('status')}")
                        
                        # Print full message (truncated if too long)
                        message_str = json.dumps(message, indent=2, ensure_ascii=False)
                        if len(message_str) > 1000:
                            print(f"\nMensagem completa (primeiros 1000 chars):\n{message_str[:1000]}...")
                        else:
                            print(f"\nMensagem completa:\n{message_str}")
                        
                    except json.JSONDecodeError as e:
                        print(f"❌ Erro ao decodificar JSON: {e}")
                        print(f"Dados recebidos: {data[:200]}...")
                
                except asyncio.TimeoutError:
                    print(".", end="", flush=True)  # Show we're still waiting
                    continue
                
    except websockets.exceptions.ConnectionRefused:
        print(f"❌ Erro: Não foi possível conectar ao WebSocket em {ws_url}")
        print("Verifique se o servidor está rodando e a porta está correta.")
        return False
    except KeyboardInterrupt:
        print(f"\n\n✅ Teste interrompido pelo usuário. Total de eventos recebidos: {event_count}")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7272
    
    print("="*60)
    print("TESTE DE WEBSOCKET - JAIson")
    print("="*60)
    print(f"Host: {host}")
    print(f"Porta: {port}")
    print("\nEnvie uma mensagem pela GUI e observe os eventos aqui.\n")
    
    asyncio.run(test_websocket(host, port))

