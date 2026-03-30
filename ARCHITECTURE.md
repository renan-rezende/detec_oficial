# Arquitetura do Sistema

## Visão de Alto Nível

O sistema é dividido em três camadas:

1. **Backend (`core/`)** — Inferência GPU e análise em processos paralelos (multiprocessing)
2. **Interface (`ui/`)** — Visualização e controle via CustomTkinter com polling não-bloqueante
3. **Utilitários (`utils/`)** — Logging e detecção de GPU

A comunicação entre o backend e a UI é feita via `mp.Queue` com política *latest-wins* (`maxsize=1`), garantindo que a UI sempre receba o frame mais recente sem acúmulo de latência.

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
            └─ Por câmera: 2 processos + 3 filas IPC
                 ├─ Processo Leitor (Reader)
                 │    └─ cv2.VideoCapture → frame_queue (maxsize=1)
                 │
                 ├─ Processo Pipeline
                 │    ├─ core/detector.py (Detector) — GPU inference
                 │    ├─ core/pellet_analyzer.py (PelletAnalyzer) — CPU post-proc
                 │    ├─ core/csv_logger.py (CSVLogger) — escrita bufferizada
                 │    └─ → data_queue (maxsize=1)
                 │
                 └─ Filas IPC
                      ├─ frame_queue   — frames do Leitor para o Pipeline
                      ├─ data_queue    — resultados do Pipeline para a UI
                      └─ config_queue  — atualizações de config da UI para o Pipeline
```

## Modelo de Processos

```
Processo Principal (UI)
  - CustomTkinter event loop
  - Polling não-bloqueante via after(30ms) → get_frame()
  - Envia atualizações de config via config_queue

Processo Leitor (por câmera)
  - Loop: cv2.VideoCapture.read() → aplicar ROI → frame_queue.put_nowait()
  - Política latest-wins: frame antigo descartado automaticamente (maxsize=1)
  - Reconexão automática em caso de falha (retry a cada 5s)

Processo Pipeline (por câmera)
  - Loop: frame_queue.get() → inferência GPU → análise CPU → log CSV → data_queue
  - Controle de taxa: sleep(max(0, 1/detection_rate − elapsed))
  - Recebe atualizações de config via config_queue sem reiniciar
  - Relatório de performance a cada 5s no log
```

## Fluxo de Dados por Frame

```
1. Leitor: cv2.VideoCapture.read()
   → frame (np.ndarray HxWx3 BGR)

2. Leitor: ROI (se configurado)
   → frame[y:y+h, x:x+w]

3. Leitor → frame_queue (put_nowait, maxsize=1)

4. Pipeline: frame_queue.get()

5. Pipeline: Detector.infer(frame)
   → YOLO Results (result.masks, result.boxes)
   → inference_time_ms

6. Pipeline: PelletAnalyzer.analyze(result, frame)
   a. Transferência GPU→CPU: result.masks.data.cpu().numpy()
   b. Redimensionamento para shape do frame original
   c. Threshold binário (> 0,5)
   d. Filtro de área mínima
   e. Cálculo vetorizado: d_px = 2 * sqrt(area / π)
   f. Conversão: d_mm = d_px * scale_mm_pixel
   g. Classificação: np.searchsorted(boundaries, diameters_mm)
   h. Centróides (com downsampling 4x para frames grandes)
   i. Anotação do frame (_annotate_frame_batch)
   → analysis_result (dict)

7. Pipeline: CSVLogger.log(analysis_result)
   → buffer em memória → flush automático a cada 0,5s
   → data/<camera_name>.csv

8. Pipeline → data_queue (put_nowait, maxsize=1)

9. UI: get_frame() → data_queue.get_nowait()
   → exibe frame + atualiza gráficos
```

## Estrutura de Dados de Análise (`PelletAnalyzer.analyze`)

```python
analysis_result = {
    'total_pellets': int,           # Pelotas detectadas no frame
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
    'range_counts': {               # Contagem de pelotas por faixa
        'range_below_6': int,
        'range_6_8': int,
        'range_8_9': int,
        'range_9_12': int,
        'range_12_16': int,
        'range_16_19': int,
        'range_above_19': int,
    },
    'range_relations': {            # Proporção por ÁREA (soma_area_mm²[faixa] / área_total_mm²)
        'range_below_6': float,
        'range_6_8': float,
        ...                         # Valores entre 0,0 e 1,0, soma ≈ 1,0
    },
    'annotated_frame': np.ndarray,  # Frame BGR anotado (ou None)
}
```

## Estrutura `CameraConfig`

```python
@dataclass
class CameraConfig:
    name: str                           # Identificador (usado como nome do CSV)
    source: str | int                   # Path, índice webcam ou URL RTSP
    model_path: str                     # Path para .engine, .onnx ou .pt
    detection_rate: float = 5.0         # Inferências por segundo
    scale_mm_pixel: float = 0.1         # Calibração mm/pixel
    confidence: float = 0.5             # Limiar YOLO
    device: str = 'cuda:0'              # Dispositivo PyTorch/ONNX
    max_det: int = 300                  # Máximo de detecções por frame
    roi: tuple | None = None            # (x, y, w, h) ou None
    frame_display_interval: float = 0   # 0 = exibir todos os frames
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

## Slot de Dados da UI

```python
# Retorno de CameraManager.get_frame(camera_id)
{
    'frame': np.ndarray,           # Frame anotado mais recente
    'analysis': dict,              # analysis_result de PelletAnalyzer
    'timestamp': float,            # time.time() do último frame
    'fps': float,                  # FPS de processamento
    'inference_time': float,       # Latência de inferência em ms
}
```

## Formatos de Modelo Suportados

| Extensão | Backend | Velocidade | Portabilidade |
|----------|---------|------------|---------------|
| `.engine` | TensorRT via Ultralytics | 60–150 FPS | GPU-específico (gerar na máquina de destino) |
| `.onnx` | ONNX Runtime | 15–30 FPS | Portável (qualquer CUDA) |
| `.pt` | PyTorch via Ultralytics | 10–20 FPS | Portável (mais lento) |

O `Detector` detecta automaticamente o formato pelo sufixo de `model_path`.

## Algoritmo de Classificação Granulométrica

```python
# config.py
GRANULOMETRIC_BOUNDARIES = [6.3, 8.0, 9.0, 12.0, 16.0, 19.0]  # mm

# pellet_analyzer.py — vetorizado (sem loop Python)
indices = np.searchsorted(GRANULOMETRIC_BOUNDARIES, diameters_mm)
# indices: 0 = abaixo de 6,3 mm ... 6 = acima de 19 mm
```

## Atualizações de Config em Tempo Real

Parâmetros atualizados sem reiniciar processos (via `config_queue`):

| Parâmetro | Efeito |
|-----------|--------|
| `detection_rate` | Ajusta sleep do loop Pipeline |
| `confidence` | Recria Detector com novo limiar |
| `scale_mm_pixel` | Recria PelletAnalyzer com nova escala |
| `max_det` | Recria Detector com novo limite |
| `roi` | Leitor passa a aplicar novo recorte |

## Otimizações de Performance

| Técnica | Localização | Impacto |
|---------|-------------|---------|
| Downsampling 4x para centróides (máscaras ≥ 400 px) | `pellet_analyzer.py` | Reduz ~112 M para ~7 M elementos |
| Operações NumPy vetorizadas | `pellet_analyzer.py` | Elimina loops Python por pelota |
| Política latest-wins (maxsize=1) | `camera_manager.py` | Evita acúmulo de latência nas filas |
| `CAP_PROP_BUFFERSIZE=1` no VideoCapture | `camera_manager.py` | Minimiza latência de captura |
| Anotação em batch via label map | `pellet_analyzer.py` | Evita loop por contorno individual |
| Pre-criação de artists matplotlib | `detection_view.py` | Evita ax.clear() a cada frame |
| Cache CSV com verificação de mtime | `detection_view.py` | Evita releituras desnecessárias |
| CSVLogger bufferizado (flush a cada 0,5s) | `csv_logger.py` | Uma abertura de arquivo por intervalo |

## Reconexão RTSP

No Processo Leitor, se `cv2.VideoCapture.read()` retornar `False`:
1. Log de aviso
2. `cap.release()`
3. `time.sleep(5)`
4. `_open_capture(source)` — nova tentativa de conexão
5. Continua loop indefinidamente

## Inicialização e Encerramento

**Startup** (`main.py`):
1. `setup_logger()` — configura logging rotativo
2. Variáveis de ambiente para modo offline YOLO (`YOLO_OFFLINE=True`, `ULTRALYTICS_OFFLINE=1`)
3. `PelletDetectorApp()` — cria janela principal
4. `app.mainloop()` — inicia event loop Tkinter

**Shutdown** (`app.on_closing()`):
1. `CameraManager.stop_all()` — envia sinal de parada para todos os processos
2. Join com timeout de 5s por processo; `terminate()` se necessário
3. Fechamento de filas e `torch.cuda.empty_cache()`
4. `app.destroy()` — fecha janela

## Logs e Monitoramento

- Arquivo: `logs/app.log` (rotativo 5 MB × 5 backups)
- Formato: `[YYYY-MM-DD HH:MM:SS] [LEVEL] module_name: message`
- A cada 5 segundos: relatório de performance do Pipeline com timings por estágio (read, infer, analyze, csv, total)
