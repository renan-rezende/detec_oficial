# Pellet Detector - Sistema de Detecção e Medição de Pelotas

Sistema completo em Python para detecção e medição automática de pelotas de minério usando visão computacional.

## ✨ Funcionalidades

- **Detecção em tempo real** usando TensorRT (60-150 FPS) ou ONNX Runtime
- **Medição automática** com classificação granulométrica em 7 faixas
- **Múltiplas câmeras** processando simultaneamente
- **Interface gráfica** moderna com CustomTkinter
- **Histórico temporal** com gráficos interativos
- **Exportação CSV** para análise posterior
- **Suporte GPU** NVIDIA com TensorRT para máxima performance

## 🚀 Performance

| Modo | GPU | FPS Típico | Latência |
|------|-----|-----------|----------|
| **TensorRT (.engine)** | RTX 3060 | 60-150 FPS | 6-15ms |
| ONNX Runtime GPU | RTX 3060 | 15-30 FPS | 30-60ms |
| ONNX Runtime CPU | - | 1-5 FPS | 200-500ms |

## Requisitos

### Software
- Python 3.8 ou superior
- GPU NVIDIA com drivers atualizados (opcional, mas recomendado)

### Dependências
```bash
pip install -r requirements.txt
```

## Estrutura do Projeto

```
detec_pellet/
├── main.py                      # Ponto de entrada
├── config.py                    # Configurações globais
├── requirements.txt             # Dependências
├── build_executable.py          # Gerador de executável
├── RGB_960m_256.engine         # Modelo ONNX/TensorRT
├── data/                        # CSVs gerados
├── logs/                        # Logs do sistema
├── core/                        # Lógica principal
│   ├── detector.py             # Detector ONNX
│   ├── pellet_analyzer.py      # Análise e classificação
│   ├── camera_manager.py       # Gerenciamento de threads
│   └── csv_logger.py           # Logger CSV
├── ui/                          # Interface gráfica
│   ├── app.py                  # App principal
│   ├── camera_form.py          # Cadastro de câmeras
│   ├── camera_list.py          # Lista de câmeras
│   ├── detection_view.py       # Visualização em tempo real
│   └── history_view.py         # Histórico temporal
└── utils/                       # Utilitários
    ├── logger.py               # Sistema de logs
    └── gpu_utils.py            # Detecção de GPUs
```

## 🎯 Seu Modelo Está Pronto!

Você já tem `RGB_960m_256.engine` (TensorRT) - **está pronto para usar!**

### Instalação TensorRT (Recomendado)

```bash
# 1. Instalar dependências base
pip install -r requirements.txt

# 2. Instalar TensorRT e PyCUDA
pip install nvidia-tensorrt pycuda

# 3. Pronto! Execute o sistema
python main.py
```

**Veja `TENSORRT_SETUP.md` para instalação detalhada do TensorRT.**

## Como Usar

### 1. Instalação

```bash
# Clonar ou extrair o projeto
cd detec_pellet

# Criar ambiente virtual (recomendado)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt
```

### 2. Converter Modelo (se necessário)

O sistema atualmente suporta modelos ONNX. Se você tem um modelo `.engine` (TensorRT), converta para ONNX:

```bash
# Exemplo usando trtexec (se disponível)
# ou use ferramentas como torch.onnx.export
```

Coloque o modelo ONNX no diretório raiz com o nome `RGB_960m_256.onnx`.

### 3. Executar Aplicação

```bash
python main.py
```

### 4. Adicionar Câmera

1. Na tela inicial, clique em **"+ Adicionar Câmera"**
2. Preencha o formulário:
   - **Nome**: Identificação da câmera (ex: "Linha 1")
   - **Caminho**: Arquivo de vídeo, índice webcam (0, 1...) ou URL RTSP
   - **Modelo**: Caminho para o modelo ONNX
   - **Taxa de Detecção**: Processar 1 a cada N frames (5 = bom equilíbrio)
   - **Escala mm/pixel**: Calibração (ex: 0.1 = 1 pixel = 0.1mm)
   - **Confiança**: Threshold do modelo (50-70% recomendado)
   - **Dispositivo**: Selecionar GPU ou CPU
3. Clique em **"Adicionar Câmera"**

### 5. Visualizar Detecções

1. Na lista de câmeras, clique em **"Visualizar"**
2. Veja o stream de vídeo com anotações
3. Acompanhe o gráfico de distribuição granulométrica em tempo real

### 6. Ver Histórico

1. Clique em **"Histórico"** na tela de câmeras
2. Selecione uma câmera ou veja todas
3. Analise a evolução temporal do tamanho médio

## Faixas Granulométricas

O sistema classifica as pelotas em 7 faixas:

- **< 6.3 mm** (`range_below_6`)
- **6.3-8 mm** (`range_6_8`)
- **8-9 mm** (`range_8_9`)
- **9-12 mm** (`range_9_12`)
- **12-16 mm** (`range_12_16`)
- **16-19 mm** (`range_16_19`)
- **> 19 mm** (`range_above_19`)

## Calibração da Escala

A escala mm/pixel deve ser calibrada para cada câmera:

1. Grave um vídeo com objeto de referência (ex: régua)
2. Meça quantos pixels correspondem a uma distância conhecida
3. Calcule: `escala = distância_mm / distância_pixels`
4. Use essa escala no cadastro da câmera

**Exemplo**: Se 100mm ocupam 500 pixels → escala = 100/500 = 0.2 mm/pixel

## CSV de Saída

Os dados são salvos em `data/detections.csv` com as seguintes colunas:

```
Data, camera_name, total_pellets, media, range_below_6, range_6_8, range_8_9,
range_9_12, range_12_16, range_16_19, range_above_19
```

As colunas de faixas contêm as **relações** (proporções de 0 a 1).

## Geração de Executável

Para criar um executável standalone:

```bash
python build_executable.py
```

O executável será gerado em `dist/PelletDetector.exe`.

**Nota**: O arquivo pode ser grande (200-500MB) devido às dependências.

## Logs

Logs são gravados em `logs/app.log` com informações sobre:
- Carregamento de modelos
- FPS de processamento
- Erros e exceções
- Ações do usuário

## Troubleshooting

### Erro: "Modelo não encontrado"
- Verifique se o arquivo do modelo existe no caminho especificado
- Certifique-se de usar um modelo ONNX (.onnx)

### Erro: "GPU não disponível"
- Instale os drivers NVIDIA mais recentes
- Instale `onnxruntime-gpu`
- Use "CPU" se não tiver GPU disponível

### Inferência muito lenta
- Reduza a resolução do vídeo
- Aumente a taxa de detecção (processar menos frames)
- Use GPU em vez de CPU
- Verifique se `onnxruntime-gpu` está instalado

### UI travando
- Reduza o número de câmeras simultâneas
- Aumente a taxa de detecção
- Feche outras aplicações pesadas

### CSV corrompido
- Os logs em `logs/app.log` contêm detalhes do erro
- Faça backup regular do CSV
- Verifique permissões da pasta `data/`

## Desenvolvimento

### Adicionar nova faixa granulométrica

1. Edite `config.py`:
   - Adicione entrada em `GRANULOMETRIC_RANGES`
   - Atualize `RANGE_ORDER` e `RANGE_LABELS`
   - Adicione coluna em `CSV_COLUMNS`

2. A classificação é automática no `pellet_analyzer.py`

### Trocar modelo

O detector suporta qualquer modelo ONNX de segmentação que retorne máscaras. Para usar outro modelo:

1. Ajuste o pré-processamento em `core/detector.py` se necessário
2. Ajuste o pós-processamento para interpretar a saída corretamente

## Licença

Este projeto foi desenvolvido como ferramenta industrial para medição de pelotas de minério.

## Suporte

Para problemas ou dúvidas, verifique os logs em `logs/app.log`.


## Obs

A versão exata do TensorRT (ex: foi gerado no TensorRT 8.5, mas você está rodando no 8.6).

A arquitetura da GPU (ex: foi gerado em uma RTX 3060, mas você está rodando em uma RTX 4090).

O Sistema Operacional e versão do CUDA.

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

pip uninstall torch torchvision torchaudio -y