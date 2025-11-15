# Funcionalidade de Escuta Contínua (VAD)

## Como Funciona

A escuta contínua usa **VAD (Voice Activity Detection)** para detectar quando o usuário está falando e automaticamente enviar o áudio quando detecta silêncio.

### Fluxo de Funcionamento

1. **Início da Escuta**: Quando o botão "Escuta Contínua" é ativado, inicia um stream de áudio contínuo
2. **Detecção de Voz**: O callback de áudio analisa cada chunk de áudio e calcula o RMS (Root Mean Square)
3. **Threshold**: Se o RMS > `voice_threshold`, considera que há voz
4. **Acumulação**: Enquanto há voz, acumula os chunks de áudio em `current_phrase_audio`
5. **Detecção de Silêncio**: Quando o RMS cai abaixo do threshold, inicia um timer de silêncio
6. **Envio Automático**: Após `silence_duration` segundos de silêncio, envia automaticamente o áudio

## Momentos em que a Escuta Pode Parar

A escuta contínua **deve** parar apenas nos seguintes casos:

### 1. Botão Desabilitado
- Quando o usuário desativa o botão "Escuta Contínua"
- Chama `stop_listening()` que fecha o stream e reseta todos os estados

### 2. Áudio da IA Sendo Reproduzido
- Quando o áudio da IA começa a tocar (`_assemble_and_play_audio`)
- Pausa temporariamente com `pause_listener()`
- Retoma automaticamente quando o áudio termina (`on_playback_complete`)

### 3. Processo de Envio para Endpoint
- **ANTES (BUG CORRIGIDO)**: A escuta era pausada ao enviar e só retomava quando o áudio da IA chegava
- **AGORA (CORRIGIDO)**: A escuta é pausada apenas durante o envio, mas é retomada imediatamente após o envio ser bem-sucedido
- A escuta só fica pausada novamente quando o áudio da IA começar a tocar

## Comportamento Atual (Otimizado)

### Fluxo de Pausa/Retomada

1. **Usuário fala** → Escuta detecta e envia automaticamente
2. **Durante envio** → Escuta pausada (muito rápido, ~100ms)
3. **Após envio bem-sucedido** → Escuta **mantém pausada** até o áudio da IA terminar
4. **Áudio da IA chega** → Começa a tocar, escuta continua pausada
5. **Áudio da IA termina** → Escuta retomada automaticamente

### Por que manter pausada?

**Vantagens:**
- ✅ Comportamento natural de conversa (não fala enquanto outro está falando)
- ✅ Evita sobreposição de áudios se a IA enviar múltiplos áudios
- ✅ Evita envio de novo áudio enquanto IA ainda está respondendo
- ✅ Melhor experiência do usuário (não precisa esperar manualmente)

**Proteções implementadas:**
- ⏱️ **Timeout de 30 segundos**: Se nenhum áudio chegar, retoma a escuta automaticamente
- ❌ **Retomada em erros**: Se houver erro no envio ou no servidor, retoma imediatamente
- 🔄 **Prevenção de sobreposição**: Se novo áudio chegar enquanto outro está tocando, para o anterior

## Estados da Escuta

- `is_listening_continuously`: Flag principal que indica se a escuta está ativa
- `continuous_stream`: Stream de áudio do sounddevice (None quando pausado)
- `_was_listening_before_playback`: Flag que indica se a escuta estava ativa antes de pausar
- `is_playing_ai_audio`: Flag que indica se o áudio da IA está sendo reproduzido
- `is_speaking`: Flag que indica se o usuário está falando no momento

## Verificações de Segurança

O callback de áudio (`_audio_callback`) verifica:
- `if self.is_playing_ai_audio: return` - Ignora áudio quando IA está falando
- `if self.is_listening_continuously:` - Só processa se a escuta estiver ativa

## Possíveis Problemas Futuros

1. **Race Condition**: Se múltiplos processos tentarem pausar/retomar simultaneamente
2. **Stream não fecha**: Se o stream não fechar corretamente, pode causar problemas
3. **Thread não inicia**: Se a thread de escuta não iniciar, a escuta não funciona

