# Referência de Módulos

Documentação de API para todos os módulos Python do projeto. Para arquitetura e fluxo de dados, ver [ARCHITECTURE.md](ARCHITECTURE.md).

---

## config.py

Constantes globais. Sem classes ou funções — apenas definições de nível de módulo.

| Constante | Tipo | Valor | Descrição |
|-----------|------|-------|-----------|
| `MODEL_PATH` | str | `'RGB_960m_256.engine'` | Caminho padrão do modelo |
| `DATA_DIR` | str | `'data'` | Diretório de saída dos CSVs |
| `LOGS_DIR` | str | `'logs'` | Diretório de logs |
| `DEFAULT_CONFIDENCE` | float | `0.5` | Limiar de confiança YOLO |
| `DEFAULT_DETECTION_RATE` | float | `5.0` | Inferências por segundo |
| `DEFAULT_SCALE_MM_PIXEL` | float | `0.1` | Escala mm/pixel padrão |
| `DEFAULT_MAX_DET` | int | `300` | Máximo de detecções por frame |
| `MODEL_INPUT_SIZE` | int | `960` | Dimensão de entrada do modelo |
| `UI_UPDATE_INTERVAL_MS` | int | `30` | Intervalo de polling da UI em ms |
| `HISTORY_UPDATE_INTERVAL_MS` | int | `5000` | Intervalo de refresh do histórico em ms |
| `GRANULOMETRIC_BOUNDARIES` | list[float] | `[6.3, 8.0, 9.0, 12.0, 16.0, 19.0]` | Limites das faixas granulométricas em mm |
| `GRANULOMETRIC_RANGE_NAMES` | list[str] | — | Nomes das 7 faixas (ordem crescente) |
| `CSV_COLUMNS` | list[str] | — | Nomes das colunas do CSV de saída |

---

## core/detector.py

### Classe `Detector`

Executa inferência YOLO. Detecta automaticamente o formato do modelo pelo sufixo do arquivo.

#### `__init__(model_path, device='cuda:0', confidence=0.5, max_det=300)`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `model_path` | str | Caminho para `.engine`, `.onnx` ou `.pt` |
| `device` | str | Dispositivo PyTorch (`'cuda:0'`, `'cpu'`) |
| `confidence` | float | Limiar de confiança mínima |
| `max_det` | int | Máximo de detecções por frame |

Para `.engine`: usa `_load_tensorrt()` (lê metadados do binding para detectar `imgsz` automaticamente).
Para `.pt` / `.onnx`: usa `_load_pytorch()` via Ultralytics.

#### `infer(frame) -> tuple[Results, float]`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `frame` | np.ndarray | Frame BGR (H×W×3) |

Retorna `(result, inference_time_ms)`.
`result` é o objeto `ultralytics.Results` com `result.masks` e `result.boxes`.

#### `cleanup() -> None`

Libera VRAM explicitamente (`torch.cuda.empty_cache()`). Chamar ao parar câmera ou fechar o app.

#### `_detect_imgsz() -> int`

Lê os metadados do engine TensorRT para determinar o tamanho de entrada automaticamente. Retorna inteiro (ex: `960`).

---

## core/pellet_analyzer.py

### Classe `PelletAnalyzer`

Pós-processa resultados YOLO para extrair métricas individuais de cada pelota.

#### `__init__(scale_mm_pixel=0.1, min_area_pixels=50)`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `scale_mm_pixel` | float | Fator de conversão pixel → mm |
| `min_area_pixels` | int | Área mínima para filtrar ruídos |

#### `analyze(result, frame=None, max_det=None) -> dict`

Pipeline principal de análise.

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `result` | ultralytics.Results | Resultado da inferência YOLO |
| `frame` | np.ndarray \| None | Frame BGR original (para anotação) |
| `max_det` | int \| None | Limite de detecções (sobrescreve instância) |

**Pipeline interno**:
1. `result.masks.data.cpu().numpy()` — transferência GPU→CPU
2. Redimensionamento das máscaras para shape do frame original
3. Threshold binário `> 0,5`
4. Filtro por `min_area_pixels`
5. `area = np.sum(mask)` por máscara (vetorizado)
6. `d_px = 2 * np.sqrt(area / np.pi)` (vetorizado)
7. `d_mm = d_px * scale_mm_pixel`
8. `np.searchsorted(GRANULOMETRIC_BOUNDARIES, d_mm)` — classificação por faixa
9. Centróides via label map com downsampling 4x (para máscaras ≥ 400 px)
10. `range_relations[faixa] = soma_area_mm²[faixa] / área_total_mm²`
11. `_annotate_frame_batch()` — anotação visual

**Retorno** — ver [ARCHITECTURE.md — Estrutura de Dados de Análise](ARCHITECTURE.md#estrutura-de-dados-de-análise-pelletanalyzeranalyze).

#### `classify_pellet(diameter_mm) -> str`

Retorna o nome da faixa granulométrica para um diâmetro dado. Usa `np.searchsorted` internamente.

#### `_annotate_frame_batch(frame, masks, pellets) -> np.ndarray`

Anota o frame com:
- Máscaras coloridas (40% opacidade, cores únicas por pelota)
- Contornos (2 px) via diferença de label map
- Rótulos de diâmetro em mm com outline preto para legibilidade

---

## core/camera_manager.py

### Classe `CameraConfig`

Dataclass de configuração de câmera. Ver campos em [ARCHITECTURE.md — Estrutura CameraConfig](ARCHITECTURE.md#estrutura-cameraconfig).

### Classe `CameraManager`

Orquestra os processos de câmera e expõe dados para a UI via filas IPC.

#### `__init__()`

Inicializa estruturas internas: `cameras` (configs), `processes` (processos reader/pipeline), `stop_events` (mp.Event por câmera), `config_queues` (atualizações de config).

#### `add_camera(config: CameraConfig) -> str`

Registra câmera, cria filas `frame_queue`, `data_queue`, `config_queue`, inicia Processo Leitor e Processo Pipeline. Retorna `config.id`.

#### `stop_camera(camera_id: str) -> None`

Sinaliza `stop_event`, aguarda join (5s timeout), chama `terminate()` se necessário e fecha filas.

#### `stop_all() -> None`

Chama `stop_camera()` para todas as câmeras registradas.

#### `get_frame(camera_id: str) -> dict | None`

Retorna o dado mais recente de `data_queue` (drena a fila para pegar o último). Retorna `None` se câmera não encontrada ou sem dados.

```python
# Estrutura retornada
{
    'frame': np.ndarray,
    'analysis': dict,       # analysis_result de PelletAnalyzer
    'timestamp': float,
    'fps': float,
    'inference_time': float,
}
```

#### `is_running(camera_id: str) -> bool`

Verifica se os processos da câmera estão vivos.

#### `update_camera_config(camera_id: str, **kwargs) -> None`

Envia atualização de parâmetros via `config_queue` sem parar os processos.
Parâmetros aceitos: `detection_rate`, `confidence`, `scale_mm_pixel`, `max_det`, `roi`.

#### `_reader_process(config, frame_queue, stop_event) -> None`

Worker do Processo Leitor. Loop: `VideoCapture.read()` → aplicar ROI → `frame_queue.put_nowait()`.

#### `_pipeline_process(config, frame_queue, data_queue, config_queue, stop_event) -> None`

Worker do Processo Pipeline. Loop: `frame_queue.get()` → `Detector.infer()` → `PelletAnalyzer.analyze()` → `CSVLogger.log()` → `data_queue.put_nowait()`. Processa `config_queue` a cada iteração.

#### `_open_capture(source) -> cv2.VideoCapture`

Cria `VideoCapture` com `CAP_PROP_BUFFERSIZE=1` para minimizar latência.

---

## core/csv_logger.py

### Classe `CSVLogger`

Logger CSV bufferizado. Um arquivo por câmera. Sem threading (roda no Processo Pipeline, único escritor).

#### `__init__(csv_path: str)`

Cria `data/<camera_name>.csv` com cabeçalho se não existir.

#### `log(camera_name: str, analysis_result: dict) -> None`

Acumula linha no buffer em memória. Flush automático a cada 0,5s (uma abertura de arquivo por intervalo).

Colunas: `Data, camera_name, total_pellets, media, range_below_6, range_6_8, range_8_9, range_9_12, range_12_16, range_16_19, range_above_19`

#### `flush() -> None`

Escreve todas as linhas acumuladas em uma única operação de arquivo.

#### `read_csv() -> pd.DataFrame`

Lê o CSV completo e retorna DataFrame Pandas.

---

## ui/app.py

### Classe `PelletDetectorApp(ctk.CTk)`

Controlador principal. Gerencia a instância de `CameraManager` e o roteamento entre telas.

#### Atributos

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `camera_manager` | CameraManager | Instância compartilhada entre telas |
| `current_frame` | ctk.CTkFrame | Tela atualmente exibida |

#### Métodos de Navegação

- `show_camera_list()` — Exibe lista de câmeras ativas
- `show_camera_form()` — Exibe formulário de cadastro
- `show_detection_view(camera_id)` — Exibe feed ao vivo da câmera
- `show_history_view()` — Abre janela separada de histórico
- `on_closing()` — Encerramento gracioso (para câmeras, libera GPU, destrói janela)

---

## ui/camera_form.py

### Classe `CameraForm(ctk.CTkFrame)`

Formulário para cadastro de nova câmera.

**Campos**: nome, source (path/URL/índice), model_path, detection_rate (slider 1–10 fps), scale_mm_pixel, confidence (slider 0–100%), max_det, frame_display_interval, device (dropdown GPU/CPU), ROI.

**Ação "Adicionar Câmera"**: valida campos, cria `CameraConfig`, chama `camera_manager.add_camera()`, navega para lista de câmeras.

---

## ui/camera_list.py

### Classe `CameraList(ctk.CTkFrame)`

Lista câmeras registradas com status e controles.

**Controles por câmera**: Visualizar (→ DetectionView), Parar, Editar (abre `EditCameraDialog`).

### Classe `EditCameraDialog(ctk.CTkToplevel)`

Diálogo modal para ajuste em tempo real de parâmetros de câmera em execução.

**Controles**: sliders de `detection_rate` e `confidence`, entries de `scale_mm_pixel` e `max_det`, gerenciamento de ROI (definir/limpar).

**Ação "Aplicar"**: chama `camera_manager.update_camera_config()` com os novos valores.

---

## ui/detection_view.py

### Classe `DetectionView(ctk.CTkFrame)`

Visualização ao vivo de uma câmera.

**Layout**: 60% painel de vídeo (esquerda) + 40% painel de gráficos (direita).

**Painel de vídeo**:
- Frame anotado redimensionado para 480p
- Overlay: FPS, total de pelotas, diâmetro médio

**Painel de gráficos**:
- Gráfico de barras (matplotlib): distribuição granulométrica em tempo real
  — artists pré-criados, alturas atualizadas sem `ax.clear()` (throttle 10×/s)
- Gráfico de linha (matplotlib): histórico de diâmetro médio
  — janela selecionável: 1h, 6h, 12h, 24h, 3d, 7d
  — dados do CSV com cache por mtime (evita releituras desnecessárias)

**Polling**: `after(30ms)` para frame, `after(5000ms)` para histórico CSV.

---

## ui/history_view.py

### Classe `HistoryView(ctk.CTkToplevel)`

Janela separada para análise histórica global.

**Funcionalidade**:
- Lê todos os CSVs de `data/`
- Gráfico de linha: evolução do diâmetro médio por câmera
- Dropdown de filtro por câmera
- Auto-refresh a cada 5 segundos

---

## ui/roi_dialog.py

### Classe `ROIDialog(ctk.CTkToplevel)`

Diálogo para seleção visual de ROI (Região de Interesse).

**Funcionalidade**:
- Captura frame da câmera e exibe em canvas
- Seleção via arrasto do mouse (retângulo)
- Campos manuais para X, Y, Largura, Altura
- Escala automática entre coordenadas de exibição e coordenadas originais
- Retorna `(x, y, w, h)` em coordenadas do frame original

---

## utils/logger.py

### Função `setup_logger(name='pellet_detector', level=logging.INFO) -> logging.Logger`

Configura e retorna logger com:
- `RotatingFileHandler`: `logs/app.log`, máx 5 MB, 5 backups
- `StreamHandler`: console
- Formato: `[%(asctime)s] [%(levelname)s] %(name)s: %(message)s`

---

## utils/gpu_utils.py

### Função `list_nvidia_gpus() -> list[dict]`

Consulta `nvidia-smi` para listar GPUs disponíveis. Fallback via ONNX Runtime se `nvidia-smi` não estiver disponível.

Retorno: `[{'index': 0, 'name': 'NVIDIA GeForce RTX 3060', 'memory_mb': 12288}, ...]`

### Função `get_gpu_options() -> list[str]`

Retorna lista formatada para o dropdown da UI. Ex: `['GPU 0: RTX 3060 (12288 MB)', 'CPU']`.

### Função `parse_device_option(option: str) -> str`

Converte string da UI para device PyTorch.
Ex: `'GPU 0: RTX 3060'` → `'cuda:0'`, `'CPU'` → `'cpu'`

---

## Scripts Auxiliares

### conv.py

Converte modelo PyTorch para TensorRT. Executar na máquina de destino (engines são GPU-específicos).

```bash
python conv.py --model RGB_960m_256.pt --device 0
# Gera: RGB_960m_256.engine
```

### convOnnx.py

Exporta modelo PyTorch para ONNX (formato portável, resolução 640×640).

```bash
python convOnnx.py
# Gera: RGB_960m_256.onnx
```

### build_executable.py

Gera executável standalone via PyInstaller (`--onedir`, obrigatório para CUDA/TensorRT).

```bash
python build_executable.py
# Saída: dist/PelletDetector/ (pasta completa)
```

### test_installation.py

Valida se todas as dependências estão corretamente instaladas e acessíveis.

### test_tensorrt.py

Testa carregamento de um modelo TensorRT e execução de inferência básica.
