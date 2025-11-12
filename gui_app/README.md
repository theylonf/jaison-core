# JAIson GUI - Interface Gráfica

Interface gráfica para controlar o servidor JAIson e interagir com a IA Aeliana via texto ou voz.

## Funcionalidades

- ✅ Iniciar/Parar servidor e plugin
- ✅ Chat por texto
- ✅ Gravação e envio de áudio do microfone
- ✅ Logs em tempo real
- ✅ Executável standalone (não precisa de terminal)

## Como Usar

### Opção 1: Executar como Script Python

```bash
cd Jaison/gui_app
conda run -n jaison-core pip install -r requirements.txt
conda run -n jaison-core python app.py
```

### Opção 2: Criar Executável (.exe)

1. **Método Simples (Windows):**
   - Dê duplo clique em `build.bat`
   - Aguarde o build terminar
   - O executável estará em `dist\JAIsonGUI.exe`

2. **Método Manual:**
   ```powershell
   cd Jaison/gui_app
   powershell -ExecutionPolicy Bypass -File build.ps1
   ```

3. **Executar o .exe:**
   - Vá até a pasta `dist`
   - Dê duplo clique em `JAIsonGUI.exe`
   - Não precisa de terminal ou Python instalado!

## Requisitos

- **Para build:** Conda com ambiente `jaison-core` OU venv Python
- **Para executar o .exe:** Nenhum (é standalone)

## Notas

- O executável inclui todas as dependências (PySide6, sounddevice, numpy, etc.)
- O arquivo .exe pode ser grande (~100-200MB) pois inclui tudo
- Você pode copiar o .exe para qualquer lugar e executar diretamente
- Certifique-se de que o servidor está rodando antes de usar o chat

## Solução de Problemas

**Erro ao gravar áudio:**
- Verifique se o microfone está conectado e habilitado
- Teste as permissões de microfone do Windows

**Servidor não conecta:**
- Verifique se o servidor está rodando na porta 7272
- Confirme o host e porta nas configurações

**Build falha:**
- Certifique-se de que o ambiente conda `jaison-core` existe
- Ou crie um venv: `python -m venv .venv`





