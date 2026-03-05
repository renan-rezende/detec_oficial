# Arquitetura do Sistema Pellet Detector

## Visão Geral

Sistema multi-threaded de detecção e medição de pelotas usando visão computacional.

```
┌─────────────────────────────────────────────────────────────────┐
│                        INTERFACE GRÁFICA                         │
│                      (CustomTkinter - Thread Principal)          │
├─────────────────────────────────────────────────────────────────┤
│  CameraForm  │  CameraList  │  DetectionView  │  HistoryView    │
└────────┬────────────┬─────────────────┬────────────────┬────────┘
         │            │                 │                │
         │            │        ┌────────▼────────┐       │
         │            │        │  Queue (Thread- │       │
         │            │        │      safe)      │       │
         │            │        └────────┬────────┘       │
         │            │                 │                │
         ▼            ▼                 ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CAMADA DE LÓGICA                          │
├─────────────────────────────────────────────────────────────────┤
│         CameraManager (Gerencia múltiplas threads)              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Thread Câmera 1                                          │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │  │
│  │  │  Detector   │→ │    Analyzer  │→ │   CSVLogger    │  │  │
│  │  │ (ONNX/GPU)  │  │ (Classificar)│  │ (Salvar dados) │  │  │
│  │  └─────────────┘  └──────────────┘  └────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Thread Câmera 2 (mesma estrutura)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Thread Câmera N (mesma estrutura)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │   data/detections.csv │
                   │   logs/app.log        │
                   └──────────────────────┘
```

## Componentes Principais

### 1. **UI Layer** (Tkinter Thread)

#### app.py
- Gerencia navegação entre telas
- Mantém referências a CameraManager e CSVLogger
- Protocolo de fechamento limpo

#### camera_form.py
- Formulário de cadastro com validação
- Detecção automática de GPUs
- File browser para vídeos e modelos

#### camera_list.py
- Lista dinâmica de câmeras ativas
- Auto-refresh a cada 2 segundos
- Botões de ação (visualizar, parar)

#### detection_view.py
- Canvas para stream de vídeo anotado
- Gráfico de barras matplotlib embedded
- Polling não-bloqueante da Queue (30ms)

#### history_view.py
- Janela independente (Toplevel)
- Gráfico temporal de múltiplas câmeras
- Filtro por câmera
- Auto-refresh a cada 5 segundos

### 2. **Core Layer** (Threads de Processamento)

#### detector.py
**Responsabilidade**: Inferência do modelo

- Carrega modelo ONNX com providers configuráveis
- Pré-processamento: resize, normalização, NCHW
- Pós-processamento: threshold, resize de volta
- Retorna: máscara binária + tempo de inferência

**Thread-safety**: Cada thread tem sua própria instância

#### pellet_analyzer.py
**Responsabilidade**: Análise morfológica

- Extrai contornos da máscara
- Calcula diâmetro usando círculo equivalente
- Classifica em faixas granulométricas
- Calcula estatísticas agregadas
- Anota frame com bounding boxes e labels

**Thread-safety**: Cada thread tem sua própria instância

#### camera_manager.py
**Responsabilidade**: Orquestração de threads

- Gerencia múltiplas câmeras simultaneamente
- Cada câmera em thread dedicada
- Queues para comunicação thread-safe
- Event flags para stop sinalização
- Reinicia vídeos quando chegam ao fim

**Thread-safety**:
- Dicts protegidos (apenas acesso, sem modificação concorrente)
- Queues thread-safe por design
- Stop flags (Event) thread-safe

#### csv_logger.py
**Responsabilidade**: Persistência de dados

- Lock para escritas concorrentes
- Append mode (modo 'a')
- Formato CSV padronizado
- Flush após cada escrita

**Thread-safety**: `threading.Lock` em todas operações de escrita

### 3. **Utils Layer**

#### logger.py
- Configuração centralizada de logging
- Handlers para arquivo e console
- Formatação padronizada

#### gpu_utils.py
- Detecção de GPUs via nvidia-smi
- Fallback para ONNX Runtime providers
- Parse de opções de UI para formato device

## Fluxo de Dados Detalhado

### Adição de Câmera

```
1. User preenche formulário → CameraForm
2. Validação → CameraConfig criada
3. CameraManager.add_camera(config)
4. Thread criada e iniciada
5. Queue criada para comunicação
6. Navegação → CameraList
```

### Processamento (Thread de Câmera)

```
Loop infinito até stop_flag:
  1. VideoCapture.read() → frame
  2. Aplicar taxa: processar 1 a cada N frames
  3. Detector.infer(frame) → mask, time
  4. PelletAnalyzer.analyze(mask, frame) → analysis
  5. CSVLogger.log(camera_name, analysis)
  6. Queue.put({frame, analysis, time})
  7. Continuar
```

### Visualização (UI Thread)

```
Polling a cada 30ms:
  1. Queue.get(timeout=0.05) → data ou None
  2. Se data disponível:
     - Atualizar canvas com frame anotado
     - Atualizar gráfico de barras
     - Atualizar labels de info
  3. after(30ms, poll_frames)
```

## Thread Safety

### Sincronização

| Componente | Mecanismo | Descrição |
|------------|-----------|-----------|
| Queue | Built-in thread-safe | Comunicação threads → UI |
| CSVLogger | threading.Lock | Escrita concorrente no CSV |
| Event flags | Built-in thread-safe | Stop sinalização |
| Detector/Analyzer | Instância por thread | Sem compartilhamento |

### Padrões Aplicados

1. **Producer-Consumer**: Threads produzem frames, UI consome
2. **Thread Pool**: CameraManager gerencia pool de threads
3. **Event-driven**: UI usa polling não-bloqueante

## Performance

### Gargalos Potenciais

1. **Inferência**:
   - GPU: ~15-60 FPS (RTX 3060)
   - CPU: ~1-5 FPS
   - Solução: Taxa de detecção

2. **UI Rendering**:
   - Máximo ~30 FPS (limitado por polling)
   - Solução: Queue com limite (descarta frames antigos)

3. **CSV Writing**:
   - Lock pode causar contenção
   - Mitigado: escrita rápida + flush

### Otimizações Implementadas

- ✅ Buffer de vídeo = 1 (reduz latência)
- ✅ Taxa de detecção configurável
- ✅ Queue limitada (descarta frames antigos)
- ✅ Resize antes de inferência
- ✅ Polling não-bloqueante na UI

## Escalabilidade

### Limites

- **Câmeras simultâneas**: 4-6 (GPU consumer grade)
- **FPS por câmera**: 10-30 (depende de GPU/CPU)
- **Resolução**: 960x960 (resize automático)

### Expansão Possível

1. **Mais câmeras**: Adicionar mais GPUs
2. **Mais FPS**: GPU mais potente
3. **Distribuído**: Separar detecção e UI

## Dependências Críticas

| Pacote | Versão | Propósito |
|--------|--------|-----------|
| customtkinter | ≥5.2 | Interface gráfica |
| opencv-python | ≥4.8 | Captura e processamento de vídeo |
| numpy | ≥1.24 | Arrays e operações numéricas |
| pandas | ≥2.0 | CSV e DataFrames |
| matplotlib | ≥3.7 | Gráficos |
| onnxruntime-gpu | ≥1.16 | Inferência em GPU |
| Pillow | ≥10.0 | Manipulação de imagens |

## Configuração

Todas configurações em `config.py`:

- Faixas granulométricas
- Caminhos de arquivos
- Constantes de UI
- Defaults de modelo

## Logging

Níveis de log por componente:

- **INFO**: Eventos importantes (câmera iniciada, FPS)
- **DEBUG**: Detalhes de processamento (contornos, inferência)
- **WARNING**: Problemas recuperáveis (GPU não encontrada)
- **ERROR**: Erros que impedem operação (modelo não carrega)
- **CRITICAL**: Erros fatais

## Próximas Melhorias Possíveis

1. **Banco de dados**: Substituir CSV por SQLite/PostgreSQL
2. **Dashboard web**: Interface web com Flask/FastAPI
3. **Alertas**: Notificações quando fora de spec
4. **Calibração automática**: Detecção automática de escala
5. **Análise estatística**: SPC, histogramas, Cp/Cpk
6. **Exportação**: PDF, Excel, relatórios automáticos
7. **Multi-idioma**: Internacionalização
8. **Themes**: Temas claro/escuro/customizado
