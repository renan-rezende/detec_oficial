# Pellet Detector

Sistema industrial em Python para detecção, medição e classificação granulométrica de pelotas de minério em tempo real, usando segmentação por instância YOLO com aceleração TensorRT/ONNX em GPU NVIDIA.

## Visão Geral

O sistema processa vídeos de câmeras industriais (arquivo, webcam, RTSP), detecta pelotas individualmente via segmentação de instâncias YOLO, calcula o diâmetro equivalente de cada pelota a partir da área real da máscara (`d = 2 * sqrt(area / pi)`), classifica em 7 faixas granulométricas e persiste os resultados em CSV por câmera. A interface gráfica (CustomTkinter) exibe o feed anotado em tempo real com gráficos de distribuição e histórico temporal.

## Estrutura de Diretórios

```
detec_pellet_sem_opc/
├── main.py                   # Ponto de entrada da aplicação
├── config.py                 # Constantes globais e configurações padrão
├── conv.py                   # Converte modelo .pt -> .engine (TensorRT)
├── convOnnx.py               # Converte modelo .pt -> .onnx
├── requirements.txt          # Dependências Python
├── build_executable.py       # Script PyInstaller para gerar executável
├── PelletDetector.spec       # Especificação PyInstaller
├── test_installation.py      # Valida dependências instaladas
├── test_tensorrt.py          # Testa carregamento TensorRT
│
├── core/                     # Módulos de processamento (backend)
│   ├── detector.py           # Inferência YOLO (TensorRT / ONNX / PyTorch)
│   ├── pellet_analyzer.py    # Pós-processamento de máscaras e classificação
│   ├── camera_manager.py     # Orquestração multi-câmera com multiprocessing
│   └── csv_logger.py         # Logger CSV bufferizado por câmera
│
├── ui/                       # Interface gráfica (CustomTkinter)
│   ├── app.py                # Controlador principal e roteamento de telas
│   ├── camera_form.py        # Formulário de cadastro de câmera
│   ├── camera_list.py        # Lista de câmeras ativas com edição
│   ├── detection_view.py     # Visualização ao vivo com gráficos
│   ├── history_view.py       # Gráfico histórico temporal
│   └── roi_dialog.py         # Seletor interativo de ROI
│
├── utils/                    # Utilitários de suporte
│   ├── logger.py             # Configuração do sistema de logs
│   └── gpu_utils.py          # Detecção e listagem de GPUs NVIDIA
│
├── Models/                   # Modelos pré-treinados (não versionados em git)
│   ├── RGB_960m_256.engine   # Modelo TensorRT principal (49 MB)
│   ├── RGB_960m_256.onnx     # Equivalente ONNX universal (90 MB)
│   ├── RGB_960m_256.pt       # Checkpoint PyTorch (45 MB)
│   ├── 399_960_nano.engine   # Variante nano TensorRT (9,2 MB)
│   └── 399_960_nano.onnx     # Variante nano ONNX (11,2 MB)
│
├── data/                     # CSVs gerados (um arquivo por câmera)
│   └── <camera_name>.csv
│
└── logs/
    └── app.log               # Log rotativo (5 MB x 5 arquivos)
```

## Quick Start

```bash
# Ambiente virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Dependências
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Executar
python main.py
```

## Parâmetros Configuráveis por Câmera

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `name` | str | — | Identificador da câmera |
| `source` | str/int | — | Arquivo de vídeo, índice webcam ou URL RTSP |
| `model_path` | str | `RGB_960m_256.engine` | Caminho para modelo .engine, .onnx ou .pt |
| `detection_rate` | float | 5.0 | Inferências por segundo (1–10) |
| `scale_mm_pixel` | float | 0.1 | Calibração: mm por pixel |
| `confidence` | float | 0.5 | Limiar de confiança YOLO (0.0–1.0) |
| `device` | str | `cuda:0` | Dispositivo de inferência |
| `max_det` | int | 300 | Máximo de detecções por frame |
| `roi` | tuple/None | None | Região de interesse `(x, y, w, h)` |
| `frame_display_interval` | float | 0 | Segundos entre frames anotados (0 = todos) |

## Faixas Granulométricas

| Código | Faixa de Diâmetro | Rótulo |
|--------|-------------------|--------|
| `range_below_6` | < 6,3 mm | Muito pequena |
| `range_6_8` | 6,3 – 8 mm | Pequena |
| `range_8_9` | 8 – 9 mm | Pequena-média |
| `range_9_12` | 9 – 12 mm | Média |
| `range_12_16` | 12 – 16 mm | Média-grande |
| `range_16_19` | 16 – 19 mm | Grande |
| `range_above_19` | > 19 mm | Muito grande |

## Formato CSV de Saída

Um arquivo por câmera em `data/<camera_name>.csv`:

```
Data,camera_name,total_pellets,media,range_below_6,range_6_8,range_8_9,range_9_12,range_12_16,range_16_19,range_above_19
2026-03-27 14:30:45,Camera_01,42,10.5,0.02,0.12,0.08,0.35,0.28,0.10,0.05
```

- `Data`: Timestamp `YYYY-MM-DD HH:MM:SS`
- `total_pellets`: Quantidade de pelotas detectadas no frame
- `media`: Diâmetro médio em mm
- `range_*`: Proporção em área de cada faixa (0,0 a 1,0, soma ≈ 1,0) — calculada como `soma_area_mm²[faixa] / área_total_mm²`, refletindo o peso relativo de cada faixa tal como no ensaio de laboratório

## Performance

| Formato de Modelo | GPU | FPS Típico | Latência por Frame |
|-------------------|-----|------------|--------------------|
| TensorRT (.engine) | RTX 3060 | 60–150 FPS | 6–15 ms |
| ONNX GPU (.onnx) | RTX 3060 | 15–30 FPS | 30–60 ms |
| PyTorch (.pt) | RTX 3060 | 10–20 FPS | 50–100 ms |

Capacidade de câmeras simultâneas (RTX 3060 com TensorRT): 3–4 câmeras.

## Conversão de Modelos

**PyTorch → TensorRT** (GPU-específico; executar na máquina de destino):

```bash
python conv.py --model RGB_960m_256.pt --device 0
# Gera: RGB_960m_256.engine
```

Ou via Ultralytics:

```python
from ultralytics import YOLO
model = YOLO('modelo.pt')
model.export(format='engine', device=0, half=True, imgsz=960)
```

**PyTorch → ONNX** (portável):

```bash
python convOnnx.py
# Gera: RGB_960m_256.onnx
```

## Geração de Executável

```bash
python build_executable.py
# Saída: dist/PelletDetector/ (pasta completa — obrigatório para CUDA/TensorRT)
```

Deploy: copiar a pasta `dist/PelletDetector/` inteira para a máquina de destino e executar `PelletDetector.exe`.

## Calibração da Escala

```
scale_mm_pixel = distancia_real_mm / distancia_pixels
```

Exemplo: 100 mm ocupando 500 pixels → `scale_mm_pixel = 0.2`

Calibrar individualmente por câmera e ângulo de câmera.

## Limitações Conhecidas

- Modelos `.engine` são específicos por GPU; usar `.onnx` para portabilidade.
- Interface Tkinter congela ao arrastar janela no Windows (comportamento normal do framework; processamento backend continua em processos separados).
- Escala deve ser calibrada individualmente por câmera/ângulo.
- TensorRT exige CUDA Toolkit compatível com o driver instalado.

## Dependências Principais

| Pacote | Uso |
|--------|-----|
| `ultralytics` | YOLO v8 (inferência, exportação) |
| `torch` / `torchvision` | Framework PyTorch com CUDA |
| `onnxruntime-gpu` | Inferência ONNX com GPU |
| `opencv-python` | Captura e processamento de frames |
| `customtkinter` | Interface gráfica moderna |
| `numpy` | Operações vetorizadas em máscaras |
| `pandas` | Leitura/escrita de CSV e análise histórica |
| `matplotlib` | Gráficos (distribuição e histórico) |

## Documentação Complementar

- [ARCHITECTURE.md](ARCHITECTURE.md) — Arquitetura de multiprocessing, fluxo de dados, filas IPC
- [MODULES.md](MODULES.md) — Referência de API por módulo (classes, métodos, inputs/outputs)
