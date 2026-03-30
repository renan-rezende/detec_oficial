# Arquitetura do Sistema

## Visão de Alto Nível

O sistema é dividido em três camadas:

1. **Backend (core/)** — Processamento de câmeras, inferência e análise em threads paralelas
2. **Interface (ui/)** — Visualização e controle via CustomTkinter com polling não-bloqueante
3. **Utilitários (utils/)** — Logging e detecção de GPU

A comunicação entre camadas é via slots de dados compartilhados (dicionário `latest_data` em `CameraManager`), sem filas bloqueantes, garantindo que a UI nunca bloqueie o processamento.

## Diagrama de Componentes

```
main.py
  └─ ui/app.py (PelletDetectorApp)
       ├─ ui/camera_form.py        # Cadastro de nova câmera
       ├─ ui/camera_list.py        # Lista e edição de câmeras ativas
       │    └─ EditCameraDialog    # Ajuste em tempo real de parâmetros
       ├─ ui/detection_view.py     # Feed ao vivo + gráficos tempo real
       ├─ ui/history_view.py       # Gráfico histórico temporal
       └─ ui/roi_dialog.py         # Seletor visual de ROI
            |
            v (cria e gerencia)
       core/camera_manager.py (CameraManager)
            ├─ CameraConfig         # Dados de configuração de uma câmera
            └─ Thread por câmera
                 ├─ cv2.VideoCapture  # Captura de frames
                 ├─ core/detector.py (Detector)
                 │    └─ Ultralytics YOLO (TensorRT ou PyTorch)
                 ├─ core/pellet_analyzer.py (PelletAnalyzer)
                 │    └─ Processamento NumPy vetorizado
                 └─ core/csv_logger.py (CSVLogger)
                      └─ pandas / threading.Lock
```

## Fluxo de Dados por Frame

```
1. Thread de câmera: cv2.VideoCapture.read()
   -> frame (np.ndarray HxWx3 BGR)

2. ROI (se configurado): frame[y:y+h, x:x+w]
   -> frame_roi

3. Detector.infer(frame_roi)
   -> YOLO Results (result.masks, result.boxes)
   -> inference_time_ms

4. PelletAnalyzer.analyze(result, frame_roi)
   a. Transferência GPU->CPU: result.masks.data.cpu().numpy()
   b. Redimensionamento para shape do frame original
   c. Threshold binário (> 0.5)
   d. Filtro de área mínima
   e. Cálculo vetorizado de diâmetros: d_px = 2 * sqrt(area / pi)
   f. Conversão: d_mm = d_px * scale_mm_pixel
   g. Classificação: np.searchsorted(boundaries, diameters)
   h. Cálculo de centróides (downsampling 4x)
   i. Anotação do frame (_annotate_frame_batch)
   -> analysis_result (dict)

5. CSVLogger.log(analysis_result, camera_name)
   -> Append em data/<camera_name>.csv (com Lock)

6. CameraManager: latest_data[camera_id] = {frame, analysis, timestamp}
   -> UI polling a cada 30ms via ctk.after()
```

## Modelo de Threads

```
Thread Principal (UI)
  - CustomTkinter event loop
  - Polling não-bloqueante via after(30ms) -> get_frame()
  - Não realiza operações pesadas

Thread de Câmera N (daemon=True)
  - Loop: captura -> inferência -> análise -> log -> sleep
  - Controle de taxa: time.sleep(1/detection_rate - elapsed)
  - Reconexão automática RTSP (retry a cada 5s)
  - Atualiza latest_data[camera_id] sem lock (assignment atômico em CPython)

Thread Logger CSV
  - Chamada síncrona de dentro da thread da câmera
  - Protected por threading.Lock por instância de CSVLogger
```

## Contexto CUDA e Compartilhamento de GPU

- Um único contexto CUDA é compartilhado entre todas as threads de câmera.
- `cv2.setNumThreads(1)` previne contenção entre OpenCV e threads Python.
- `CAP_PROP_BUFFERSIZE=1` minimiza buffer do VideoCapture para reduzir latência.
- Cleanup explícito de VRAM via `Detector.cleanup()` ao parar câmera ou fechar app.

## Estrutura de Dados de Análise (PelletAnalyzer.analyze)

```python
analysis_result = {
    'total_pellets': int,           # N pelotas detectadas no frame
    'media': float,                 # Diâmetro médio em mm
    'pellets': [                    # Lista de dicts por pelota
        {
            'center': (int, int),       # Centróide (x, y) em pixels
            'area_pixels': int,          # Área da máscara em pixels
            'area_mm2': float,           # Área em mm²
            'diameter_px': float,        # Diâmetro equivalente em pixels
            'diameter_mm': float,        # Diâmetro equivalente em mm
            'range': str,               # Ex: 'range_9_12'
        },
        ...
    ],
    'range_counts': {               # Contagem por faixa
        'range_below_6': int,
        'range_6_8': int,
        ...
    },
    'range_relations': {            # Proporção por ÁREA (0.0 a 1.0) — soma_area_mm²[faixa] / área_total_mm²
        'range_below_6': float,
        'range_6_8': float,
        ...
    },
    'annotated_frame': np.ndarray,  # Frame BGR anotado (ou None)
}
```

## Estrutura CameraConfig

```python
@dataclass
class CameraConfig:
    name: str                       # Identificador (usado como nome do CSV)
    source: str | int               # Path, índice webcam ou URL RTSP
    model_path: str                 # Path para .engine ou .onnx
    detection_rate: float = 5.0    # Inferências por segundo
    scale_mm_pixel: float = 0.1    # Calibração mm/pixel
    confidence: float = 0.5        # Limiar YOLO
    device: str = 'cuda:0'         # Dispositivo PyTorch/ONNX
    max_det: int = 300             # Máximo de detecções por frame
    roi: tuple | None = None       # (x, y, w, h) ou None
    frame_display_interval: float = 0  # 0 = exibir todos os frames
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

## Slot de Dados da UI (latest_data)

```python
# CameraManager.latest_data[camera_id]
{
    'frame': np.ndarray,           # Frame anotado mais recente
    'analysis': dict,              # Resultado de analysis_result
    'timestamp': float,            # time.time() do último frame
    'fps': float,                  # FPS de processamento
    'inference_time': float,       # Latência de inferência em ms
}
```

## Formatos de Modelo Suportados

| Extensão | Backend | Detecção | Notas |
|----------|---------|----------|-------|
| `.engine` | TensorRT via Ultralytics | Pelo sufixo | GPU-específico; gerado localmente |
| `.pt` | PyTorch via Ultralytics | Pelo sufixo | Portável; mais lento |
| `.onnx` | Ultralytics (ONNX Runtime) | Pelo sufixo | Portável; médio desempenho |

O `Detector` detecta automaticamente o formato pelo sufixo do arquivo (`model_path`).

## Módulo de Detecção de Tamanho de Entrada

`Detector._detect_imgsz()` lê os metadados do modelo TensorRT para determinar automaticamente o tamanho de entrada (ex: 960x960), evitando hardcoding.

## Reconexão RTSP

Na thread de câmera, se `cv2.VideoCapture.read()` retornar `False`:
1. Log de aviso
2. `cap.release()`
3. `time.sleep(5)`
4. `_open_capture(source)` — nova tentativa de conexão
5. Continua loop indefinidamente

## Algoritmo de Classificação Granulométrica

```python
# config.py
GRANULOMETRIC_BOUNDARIES = [6.3, 8.0, 9.0, 12.0, 16.0, 19.0]  # mm
GRANULOMETRIC_RANGE_NAMES = [
    'range_below_6', 'range_6_8', 'range_8_9',
    'range_9_12', 'range_12_16', 'range_16_19', 'range_above_19'
]

# pellet_analyzer.py — vetorizado
indices = np.searchsorted(GRANULOMETRIC_BOUNDARIES, diameters_mm)
# indices: 0 = abaixo de 6.3mm, 6 = acima de 19mm
```

## Otimizações de Performance

| Técnica | Localização | Impacto |
|---------|-------------|---------|
| Downsampling 4x para centróides | `pellet_analyzer.py` | Reduz de ~112M para ~7M elementos |
| Operações NumPy vetorizadas | `pellet_analyzer.py` | Elimina loops Python por pelota |
| `cv2.setNumThreads(1)` | `camera_manager.py` | Previne contenção de threads OpenCV |
| `CAP_PROP_BUFFERSIZE=1` | `camera_manager.py` | Minimiza latência de captura |
| Anotação batch por label map | `pellet_analyzer.py` | Evita loop por contorno |
| Contexto CUDA compartilhado | `camera_manager.py` | Uma inicialização GPU por processo |

## Inicialização e Encerramento

**Startup** (`main.py`):
1. `setup_logger()` — configura logging rotativo
2. Variáveis de ambiente para modo offline YOLO (`YOLO_OFFLINE=True`)
3. `PelletDetectorApp()` — cria janela principal
4. `app.mainloop()` — inicia event loop Tkinter

**Shutdown** (`app.on_closing()`):
1. `CameraManager.stop_all()` — sinaliza threads para parar
2. `Detector.cleanup()` por câmera — libera VRAM
3. `app.destroy()` — fecha janela

## Logs e Monitoramento

- Arquivo: `logs/app.log` (rotativo 5 MB x 5 backups)
- Formato: `[YYYY-MM-DD HH:MM:SS] [LEVEL] module_name: message`
- A cada 5 segundos por thread de câmera: relatório de performance com timings de cada estágio (read, infer, analyze, csv, total)
