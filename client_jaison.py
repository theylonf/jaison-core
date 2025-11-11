import json
import asyncio
import websockets
import requests
import time

API_URL = "http://127.0.0.1:7272"
WS_URL = "ws://127.0.0.1:7272"

# Função para enviar uma mensagem ao contexto
def send_message(user, content):
    # Sempre incluir timestamp válido (Unix timestamp em segundos)
    timestamp = int(time.time())
    body = {
        "user": user, 
        "content": content,
        "timestamp": timestamp
    }
    response = requests.post(f"{API_URL}/api/context/conversation/text",
                             headers={"Content-Type": "application/json"},
                             data=json.dumps(body).encode("utf-8"))
    if response.status_code != 200:
        print(f"❌ Erro ao enviar mensagem: {response.text}")
        return None
    job_id = response.json().get("response", {}).get("job_id")
    print(f"📨 Mensagem enviada! job_id={job_id}")
    return job_id


# Função para pedir uma resposta
def generate_response():
    try:
        response = requests.post(f"{API_URL}/api/response",
                                 headers={"Content-Type": "application/json"},
                                 data="{}",
                                 timeout=30)
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ Erro ao gerar resposta (status {response.status_code}): {error_text}")
            
            # Verificar se é erro de API key
            if "API key" in error_text or "invalid_api_key" in error_text:
                print("\n⚠️  PROBLEMA DE API KEY DETECTADO!")
                print("   Verifique seu arquivo .env e certifique-se de que:")
                print("   1. A chave OPENAI_API_KEY está configurada corretamente")
                print("   2. A chave NÃO contém os símbolos < > (remova-os)")
                print("   3. A chave é válida e tem créditos disponíveis")
                print("   Exemplo correto: OPENAI_API_KEY=sk-...")
                print("   Exemplo ERRADO: OPENAI_API_KEY=<sk-...>")
            
            return None
        job_id = response.json().get("response", {}).get("job_id")
        print(f"⚙️  Gerando resposta... job_id={job_id}")
        return job_id
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão ao gerar resposta: {e}")
        return None


# Função para verificar operações carregadas
def get_loaded_operations():
    """Obtém lista de operações carregadas, incluindo t2t"""
    try:
        response = requests.get(f"{API_URL}/api/operations",
                               headers={"Content-Type": "application/json"},
                               timeout=10)
        if response.status_code != 200:
            print(f"❌ Erro ao obter operações: {response.text}")
            return None
        data = response.json()
        operations = data.get("response", {})
        print(f"📋 Operações carregadas:")
        for role, op_id in operations.items():
            if isinstance(op_id, list):
                print(f"   {role}: {', '.join(op_id)}")
            else:
                print(f"   {role}: {op_id}")
        return operations
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão ao obter operações: {e}")
        return None


# Função para usar t2t diretamente
def use_t2t(instruction_prompt, messages, t2t_id=None):
    """
    Usa a operação t2t diretamente
    
    Args:
        instruction_prompt: Prompt de instrução do sistema
        messages: Lista de mensagens no formato [{"role": "user", "content": "..."}, ...]
        t2t_id: ID específico da operação t2t (opcional, usa o padrão se não especificado)
    """
    payload = {
        "role": "t2t",
        "payload": {
            "instruction_prompt": instruction_prompt,
            "messages": messages
        }
    }
    
    # Se especificou um ID específico, adiciona ao payload
    if t2t_id:
        payload["id"] = t2t_id
    
    try:
        response = requests.post(f"{API_URL}/api/operations/use",
                                headers={"Content-Type": "application/json"},
                                data=json.dumps(payload).encode("utf-8"),
                                timeout=30)
        if response.status_code != 200:
            error_text = response.text
            print(f"❌ Erro ao usar t2t (status {response.status_code}): {error_text}")
            return None
        job_id = response.json().get("response", {}).get("job_id")
        print(f"⚙️  Usando t2t... job_id={job_id}")
        return job_id
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão ao usar t2t: {e}")
        return None


# Modo debug - defina como True para ver todos os eventos
DEBUG = True

# Função para processar um evento individual
async def process_event(data):
    """Processa um evento individual do WebSocket"""
    if DEBUG:
        print(f"[DEBUG] Evento recebido: {json.dumps(data, indent=2, ensure_ascii=False)}")
    
    # A estrutura é: {"status": 200, "message": "job_type", "response": {...}}
    job_type = data.get("message", "")
    response_data = data.get("response", {})
    result = response_data.get("result", {})
    finished = response_data.get("finished", False)
    job_id = response_data.get("job_id", "")

    # Eventos do job "response" - quando a resposta está pronta
    if job_type == "response":
        if finished:
            if response_data.get("success", False):
                print("✅ Resposta gerada com sucesso!")
            else:
                error = result.get("reason", "Erro desconhecido")
                error_type = result.get("type", "unknown")
                print(f"❌ Erro ao gerar resposta ({error_type}): {error}")
        else:
            # Durante o processamento, procurar por conteúdo de texto
            if "content" in result:
                text = result.get("content", "")
                if text:
                    print(f"\n🤖 Sammy: {text}\n")
            # Mostrar outros eventos durante processamento (debug)
            elif DEBUG:
                print(f"[DEBUG] Evento 'response' intermediário: {list(result.keys())}")

    # Eventos do job "context_conversation_add_text" - quando mensagem é adicionada
    elif job_type == "context_conversation_add_text":
        if finished:
            content = result.get("content", "")
            user = result.get("user", "")
            print(f"💬 {user}: {content}")

    # Eventos do job "operation_use" - quando uma operação é usada diretamente (ex: t2t)
    elif job_type == "operation_use":
        if finished:
            if response_data.get("success", False):
                # Tentar obter o conteúdo gerado
                if "content" in result:
                    content = result.get("content", "")
                    print(f"\n✅ T2T concluído! Resultado:\n{content}\n")
                else:
                    print("✅ Operação concluída com sucesso!")
            else:
                error = result.get("reason", "Erro desconhecido")
                error_type = result.get("type", "unknown")
                print(f"❌ Erro na operação ({error_type}): {error}")
        else:
            # Durante o processamento, mostrar chunks de conteúdo
            if "content" in result:
                content_chunk = result.get("content", "")
                if content_chunk:
                    print(content_chunk, end="", flush=True)
            elif DEBUG:
                print(f"[DEBUG] Evento 'operation_use' intermediário: {list(result.keys())}")

    # Outros eventos
    else:
        if DEBUG or job_type in ["context_request_add", "context_clear"]:
            if not finished:
                print(f"🧠 {job_type} (job_id: {job_id})")
            else:
                print(f"🧠 {job_type} concluído")


# Função assíncrona para ouvir o WebSocket
async def listen_for_response():
    print("🎧 Conectando ao WebSocket...")
    try:
        async with websockets.connect(WS_URL) as ws:
            print("✅ WebSocket conectado!")
            while True:
                try:
                    message = await ws.recv()
                    data = json.loads(message)

                    # Pode ser uma lista ou um dicionário
                    if isinstance(data, list):
                        # Se for uma lista, processar cada item
                        for item in data:
                            if isinstance(item, dict):
                                await process_event(item)
                    elif isinstance(data, dict):
                        # Se for um dicionário, processar diretamente
                        await process_event(data)
                    else:
                        print(f"⚠️ Formato desconhecido: {type(data)}")
                        if DEBUG:
                            print(f"   Dados: {data}")
                except KeyboardInterrupt:
                    print("❌ Encerrando WebSocket.")
                    break
                except Exception as e:
                    print(f"❌ Erro ao processar mensagem WebSocket: {e}")
                    if DEBUG:
                        import traceback
                        traceback.print_exc()
                    # Continuar tentando receber mensagens
    except Exception as e:
        print(f"❌ Erro ao conectar WebSocket: {e}")
        print("   Certifique-se de que o servidor está rodando!")
        import traceback
        traceback.print_exc()


# Modo de teste t2t
async def test_t2t_mode():
    """Modo para testar t2t diretamente"""
    print("=== Modo de Teste T2T ===")
    print("Digite 'sair' para voltar ao menu principal.\n")
    
    # Conecta ao WebSocket em segundo plano
    listener_task = asyncio.create_task(listen_for_response())
    await asyncio.sleep(1)
    
    # Verificar operações carregadas
    print("Verificando operações carregadas...")
    operations = get_loaded_operations()
    t2t_id = None
    if operations and "t2t" in operations:
        t2t_id = operations["t2t"]
        print(f"✅ T2T encontrado: {t2t_id}\n")
    else:
        print("⚠️  Nenhuma operação t2t carregada. Usando padrão.\n")
    
    # Prompt de sistema padrão (pode ser modificado)
    instruction_prompt = "Você é um assistente útil e amigável."
    
    while True:
        print("\n" + "="*50)
        print("Opções:")
        print("  1. Testar com prompt padrão")
        print("  2. Testar com prompt personalizado")
        print("  3. Alterar prompt de sistema")
        print("  4. Ver operações carregadas")
        print("  'sair' - Voltar ao menu principal")
        print("="*50)
        
        choice = input("\nEscolha uma opção: ").strip()
        
        if choice.lower() in ["sair", "exit", "quit"]:
            break
        elif choice == "1":
            user_msg = input("\n💬 Digite sua mensagem: ")
            if not user_msg:
                continue
            messages = [{"role": "user", "content": user_msg}]
            print(f"\n📤 Enviando para t2t...")
            print(f"   Prompt de sistema: {instruction_prompt}")
            print(f"   Mensagem: {user_msg}\n")
            use_t2t(instruction_prompt, messages, t2t_id)
            await asyncio.sleep(0.5)
        elif choice == "2":
            custom_prompt = input("\n📝 Digite o prompt de sistema: ")
            if not custom_prompt:
                continue
            user_msg = input("💬 Digite sua mensagem: ")
            if not user_msg:
                continue
            messages = [{"role": "user", "content": user_msg}]
            print(f"\n📤 Enviando para t2t...")
            print(f"   Prompt de sistema: {custom_prompt}")
            print(f"   Mensagem: {user_msg}\n")
            use_t2t(custom_prompt, messages, t2t_id)
            await asyncio.sleep(0.5)
        elif choice == "3":
            new_prompt = input("\n📝 Digite o novo prompt de sistema: ")
            if new_prompt:
                instruction_prompt = new_prompt
                print(f"✅ Prompt de sistema atualizado!")
        elif choice == "4":
            get_loaded_operations()
        else:
            print("❌ Opção inválida!")
    
    listener_task.cancel()
    print("\n👋 Saindo do modo de teste T2T.")


# Loop principal de chat
async def main():
    print("=== Chat com Project J.A.I.son ===")
    print("Escolha o modo:")
    print("  1. Chat normal (usando pipeline completo)")
    print("  2. Teste T2T (testar t2t diretamente)")
    print("  'sair' - Encerrar\n")
    
    mode = input("Escolha o modo: ").strip()
    
    if mode == "2":
        await test_t2t_mode()
        return
    elif mode.lower() in ["sair", "exit", "quit"]:
        return
    elif mode != "1":
        print("Modo inválido, usando chat normal...\n")
    
    print("=== Chat Normal ===")
    print("Digite 'sair' para encerrar.\n")

    # Conecta ao WebSocket em segundo plano
    listener_task = asyncio.create_task(listen_for_response())
    
    # Pequeno delay para garantir que o WebSocket está conectado
    await asyncio.sleep(1)

    user = "Usuario"
    while True:
        msg = input("💬 Você: ")
        if msg.lower() in ["sair", "exit", "quit"]:
            break
        send_message(user, msg)
        # Pequeno delay para garantir que a mensagem foi processada
        await asyncio.sleep(0.5)
        generate_response()

    listener_task.cancel()
    print("👋 Chat encerrado.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Encerrado pelo usuário.")
