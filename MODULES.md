# Referência de Módulos

Documentação de API para todos os módulos Python do projeto. Para arquitetura e fluxo de dados, ver [ARCHITECTURE.md](ARCHITECTURE.md).

---

## config.py

Constantes globais. Não contém classes ou funções — apenas definições de nível de módulo.

| Constante | Tipo | Valor Padrão | Descrição |
|-----------|------|--------------|-----------|
| `MODEL_PATH` | str | `'RGB_960m_256.engine'` | Caminho padrão do modelo |
| `DATA_DIR` | str | `'data'` | Diretório de saída de CSVs |
| `LOGS_DIR` | str | `'logs'` | Diretório de logs |
| `DEFAULT_CONFIDENCE` | float | `0.5` | Limiar de confiança YOLO |
| `DEFAULT_DETECTION_RATE` | float | `5.0` | Inferências por segundo |
| `DEFAULT_SCALE_MM_PIXEL` | float | `0.1` | Escala mm/pixel padrão |
| `DEFAULT_MAX_DET` | int | `300` | Máximo de detecções por frame |
| `MODEL_INPUT_SIZE` | int | `960` | Dimensão de entrada do modelo |
| `UI_UPDATE_INTERVAL_MS` | int | `30` | Intervalo de polling da UI em ms |
| `HISTORY_UPDATE_INTERVAL_MS` | int | `5000` | Intervalo de refresh do histórico |
| `GRANULOMETRIC_RANGES` | dict | — | Mapeamento nome -> (min, max) em mm |
| `CSV_COLUMNS` | list | — | Nomes das colunas do CSV de saída |

---

## core/detector.py

### Classe `Detector`

Executa inferência YOLO. Detecta automaticamente o formato do modelo (.engine, .onnx, .pt).

#### `__init__(model_path, device='cuda:0', confidence=0.5, max_det=300)`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `model_path` | str | Caminho para arquivo do modelo |
| `device` | str | Dispositivo PyTorch (`'cuda:0'`, `'cpu'`) |
| `confidence` | float | Limiar de confiança mínima |
| `max_det` | int | Máximo de detecções por frame |

Carrega o modelo na memória GPU. Para `.engine`, usa `_load_tensorrt()`. Para `.pt` ou `.onnx`, usa `_load_pytorch()`.

#### `infer(frame) -> tuple[Results, float]`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `frame` | np.ndarray | Frame BGR (HxWx3) |

Retorna `(result, inference_time_ms)` onde `result` é o objeto `ultralytics.Results` com `result.masks` e `result.boxes`.

#### `cleanup() -> None`

Libera VRAM explicitamente. Deve ser chamado ao parar uma câmera ou ao fechar o aplicativo.

#### `_detect_imgsz() -> int`

Lê os metadados do engine TensorRT para determinar automaticamente o tamanho de entrada do modelo. Retorna inteiro (ex: `960`).

---

## core/pellet_analyzer.py

### Classe `PelletAnalyzer`

Pós-processa resultados YOLO para extrair métricas individuais de cada pelota.

#### `__init__(scale_mm_pixel=0.1, min_area_pixels=100)`

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `scale_mm_pixel` | float | Fator de conversão pixel -> mm |
| `min_area_pixels` | int | Área mínima para filtrar ruídos |

#### `analyze(result, frame) -> dict`

Pipeline principal de análise.

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `result` | ultralytics.Results | Resultado da inferência YOLO |
| `frame` | np.ndarray | Frame BGR original |

**Retorno** — dicionário `analysis_result`:

```python
{
    'total_pellets': int,
    'media': float,                 # mm
    'pellets': [
        {
            'center': (int, int),
            'area_pixels': int,
            'area_mm2': float,
            'diameter_px': float,
            'diameter_mm': float,
            'range': str,           # Ex: 'range_9_12'
        }
    ],
    'range_counts': {str: int},     # contagem de pelotas por faixa
    'range_relations': {str: float}, # proporção por ÁREA: soma_area_mm²[faixa] / área_total_mm²
    'annotated_frame': np.ndarray | None,
}
```

**Pipeline interno**:
1. `result.masks.data.cpu().numpy()` — transferência GPU->CPU
2. Redimensionamento das máscaras para shape do frame original
3. Threshold binário `> 0.5`
4. Filtro por área mínima
5. `area = np.sum(mask)` por máscara
6. `d_px = 2 * np.sqrt(area / np.pi)` — vetorizado
7. `d_mm = d_px * scale_mm_pixel`
8. `np.searchsorted(boundaries, d_mm)` — classificação por faixa de diâmetro
9. Centróides via downsampling 4x
10. `range_relations[faixa] = soma_area_mm²[faixa] / área_total_mm²` — proporção por área (proxy de massa)
11. `_annotate_frame_batch()` — anotação do frame

#### `classify_pellet(diameter_mm) -> str`

Retorna o nome da faixa granulométrica para um diâmetro dado. Usa `np.searchsorted` internamente.

#### `_annotate_frame_batch(frame, masks, pellets) -> np.ndarray`

Anota o frame com:
- Máscaras coloridas (40% opacidade, cores únicas por pelota)
- Contornos verdes (2px) via diferença de label map
- Labels de diâmetro em mm com outline preto para legibilidade

---

## core/camera_manager.py

### Classe `CameraConfig`

Dataclass de configuração de câmera. Ver campos em [ARCHITECTURE.md — Estrutura CameraConfig](ARCHITECTURE.md#estrutura-cameraconfig).

### Classe `CameraManager`

Orquestra threads de câmera e expõe dados para a UI.

#### `__init__()`

Inicializa estruturas internas: `cameras` (dict de configs), `threads` (dict de threads), `latest_data` (slots de dados), `loggers` (CSVLoggers por câmera).

#### `add_camera(config: CameraConfig) -> str`

Registra câmera, cria `CSVLogger`, `Detector` e `PelletAnalyzer`, inicia thread daemon. Retorna `config.id`.

#### `stop_camera(camera_id: str) -> None`

Sinaliza thread para parar, aguarda join, chama `Detector.cleanup()`.

#### `stop_all() -> None`

Chama `stop_camera()` para todas as câmeras registradas.

#### `get_frame(camera_id: str) -> dict | None`

Retorna o slot `latest_data[camera_id]` sem bloqueio. Retorna `None` se câmera não encontrada ou sem dados.

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

Verifica se a thread da câmera está viva.

#### `update_camera_config(camera_id: str, **kwargs) -> None`

Atualiza parâmetros em tempo real sem parar a câmera. Parâmetros aceitos: `detection_rate`, `confidence`, `scale_mm_pixel`, `max_det`, `roi`. Recria `Detector` e `PelletAnalyzer` internamente se necessário.

#### `_process_camera(config: CameraConfig) -> None`

Método de worker da thread. Loop principal:
```
while running:
    frame = cap.read()
    if not frame: reconnect()
    if roi: frame = frame[roi]
    result, t_infer = detector.infer(frame)
    analysis = analyzer.analyze(result, frame)
    logger.log(analysis, config.name)
    latest_data[id] = {...}
    sleep(max(0, 1/detection_rate - elapsed))
    every 5s: log performance report
```

#### `_open_capture(source) -> cv2.VideoCapture`

Cria `VideoCapture` com `CAP_PROP_BUFFERSIZE=1` para minimizar latência.

---

## core/csv_logger.py

### Classe `CSVLogger`

Logger CSV thread-safe. Um arquivo por câmera.

#### `__init__(camera_name: str, data_dir: str = 'data')`

Cria `data/<camera_name>.csv` com cabeçalho se não existir.

#### `log(analysis_result: dict, camera_name: str) -> None`

Appenda uma linha ao CSV. Thread-safe via `threading.Lock`.

Colunas escritas: `Data, camera_name, total_pellets, media, range_below_6, range_6_8, range_8_9, range_9_12, range_12_16, range_16_19, range_above_19`

#### `read_csv() -> pd.DataFrame`

Lê o CSV completo e retorna DataFrame Pandas.

#### `get_history_for_camera(camera_name: str, limit: int = 1000) -> pd.DataFrame`

Filtra por `camera_name` e retorna as últimas `limit` linhas.

#### `get_latest_stats() -> dict | None`

Retorna a última linha do CSV como dicionário. Retorna `None` se vazio.

#### `clear() -> None`

Limpa o CSV mantendo o cabeçalho.

---

## ui/app.py

### Classe `PelletDetectorApp(ctk.CTk)`

Controlador principal. Gerencia a instância de `CameraManager` e roteamento entre telas.

#### Atributos

| Atributo | Tipo | Descrição |
|----------|------|-----------|
| `camera_manager` | CameraManager | Instância compartilhada entre telas |
| `current_frame` | ctk.CTkFrame | Frame atualmente exibido |

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

**Campos**: nome, source (path/URL/índice), model_path, detection_rate (slider 1–10), scale_mm_pixel, confidence (slider 0–100%), max_det, frame_display_interval, device (dropdown GPU/CPU), ROI.

**Ação "Adicionar Câmera"**: Valida campos, cria `CameraConfig`, chama `camera_manager.add_camera()`, navega para lista.

---

## ui/camera_list.py

### Classe `CameraList(ctk.CTkFrame)`

Lista câmeras registradas com status e controles.

**Controles por câmera**: Visualizar, Parar, abrir `EditCameraDialog`.

### Classe `EditCameraDialog(ctk.CTkToplevel)`

Diálogo modal para ajuste em tempo real de parâmetros de câmera em execução.

**Controles**: sliders de `detection_rate` e `confidence`, entries de `scale_mm_pixel` e `max_det`, gestão de ROI (definir/limpar).

**Ação "Aplicar"**: Chama `camera_manager.update_camera_config()` com os novos valores.

---

## ui/detection_view.py

### Classe `DetectionView(ctk.CTkFrame)`

Visualização ao vivo de uma câmera.

**Layout**: 60% painel de vídeo (esquerda) + 40% painel de gráficos (direita).

**Painel de vídeo**:
- Frame anotado redimensionado para exibição
- Overlay de texto: FPS, total de pelotas, diâmetro médio

**Painel de gráficos**:
- Gráfico de barras (matplotlib): distribuição granulométrica em tempo real
- Gráfico de linha (matplotlib): histórico de diâmetro médio com seletor de janela temporal (1h, 6h, 12h, 24h, 3d, 7d)

**Polling**: `after(30ms)` para frame, `after(5000ms)` para histórico.

---

## ui/history_view.py

### Classe `HistoryView(ctk.CTkToplevel)`

Janela separada para análise histórica.

**Funcionalidade**:
- Lê todos os CSVs de `data/`
- Gráfico de linha: evolução do diâmetro médio por câmera
- Dropdown de filtro por câmera
- Auto-refresh a cada 5 segundos

---

## ui/roi_dialog.py

### Classe `ROIDialog(ctk.CTkToplevel)`

Diálogo para seleção visual de ROI (Region of Interest).

**Funcionalidade**:
- Captura frame da câmera e exibe em canvas
- Seleção via arrastar mouse (retângulo)
- Campos manuais para X, Y, Largura, Altura
- Escala automática entre coordenadas de exibição e coordenadas originais
- Retorna `(x, y, w, h)` em coordenadas do frame original

---

## utils/logger.py

### Função `setup_logger(name='pellet_detector', level=logging.INFO) -> logging.Logger`

Configura e retorna logger com:
- `RotatingFileHandler`: `logs/app.log`, max 5 MB, 5 backups
- `StreamHandler`: console
- Formato: `[%(asctime)s] [%(levelname)s] %(name)s: %(message)s`

---

## utils/gpu_utils.py

### Função `list_nvidia_gpus() -> list[dict]`

Consulta `nvidia-smi` para listar GPUs disponíveis. Fallback via ONNX Runtime se nvidia-smi não disponível.

Retorno: `[{'index': 0, 'name': 'NVIDIA GeForce RTX 3060', 'memory_mb': 12288}, ...]`

### Função `get_gpu_options() -> list[str]`

Retorna lista formatada para dropdown da UI. Ex: `['GPU 0: RTX 3060 (12288 MB)', 'CPU']`.

### Função `parse_device_option(option: str) -> str`

Converte string de opção da UI para string de device PyTorch.

Ex: `'GPU 0: RTX 3060'` -> `'cuda:0'`, `'CPU'` -> `'cpu'`

---

## Scripts Auxiliares

### conv.py

Converte modelo PyTorch para TensorRT. Deve ser executado na máquina de destino (engines são GPU-específicos).

```bash
python conv.py --model RGB_960m_256.pt --device 0
# Gera: RGB_960m_256.engine
```

### convOnnx.py

Exporta modelo PyTorch para ONNX (formato portável).

```bash
python convOnnx.py
# Gera: RGB_960m_256.onnx (resolução 640x640)
```

### build_executable.py

Gera executável standalone via PyInstaller.

```bash
python build_executable.py
# Saída: dist/PelletDetector/ (pasta — não arquivo único)
```

O build usa `--onedir` (obrigatório para CUDA/TensorRT). Copiar a pasta inteira para o servidor de destino.

### test_installation.py

Valida se todas as dependências estão corretamente instaladas e acessíveis.

### test_tensorrt.py

Testa carregamento de um modelo TensorRT e execução de inferência básica.
