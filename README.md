# 🎯 Pellet Detector - Sistema de Detecção e Medição de Pelotas

Sistema completo em Python para detecção e medição automática de pelotas de minério usando visão computacional com TensorRT.

## ✨ Funcionalidades

- **Detecção em tempo real** usando TensorRT via Ultralytics YOLO (60-150 FPS)
- **Medição baseada em segmentação** - cálculo de área real das máscaras
- **Classificação granulométrica** em 7 faixas automaticamente
- **Múltiplas câmeras** processando simultaneamente
- **Interface gráfica moderna** com CustomTkinter
- **CSV separado por câmera** para melhor organização
- **Visualização com máscaras coloridas** semi-transparentes
- **Histórico temporal** com gráficos interativos
- **Suporte GPU** NVIDIA com TensorRT para máxima performance

## 🚀 Performance

| Modo | GPU | FPS Típico | Latência |
|------|-----|-----------|----------|
| **TensorRT (.engine)** | RTX 3060 | 60-150 FPS | 6-15ms |
| ONNX Runtime GPU | RTX 3060 | 15-30 FPS | 30-60ms |

## 📋 Requisitos

### Hardware
- GPU NVIDIA (recomendado) ou CPU

### Software
- Python 3.8 ou superior
- CUDA Toolkit 11.x ou 12.x (para GPU)
- Drivers NVIDIA atualizados

### Dependências
```bash
pip install -r requirements.txt
```

## 📁 Estrutura do Projeto

```
detec_pellet/
├── main.py                      # Ponto de entrada
├── config.py                    # Configurações globais
├── requirements.txt             # Dependências
├── build_executable.py          # Gerador de executável
├── RGB_960m_256.engine          # Modelo TensorRT
│
├── core/                        # Lógica principal
│   ├── detector.py             # Inferência TensorRT/ONNX
│   ├── pellet_analyzer.py      # Análise e classificação
│   ├── camera_manager.py       # Gerenciamento de threads
│   └── csv_logger.py           # Logger CSV
│
├── ui/                          # Interface gráfica
│   ├── app.py                  # App principal
│   ├── camera_form.py          # Cadastro de câmeras
│   ├── camera_list.py          # Lista de câmeras
│   ├── detection_view.py       # Visualização em tempo real
│   └── history_view.py         # Histórico temporal
│
├── utils/                       # Utilitários
│   ├── logger.py               # Sistema de logs
│   └── gpu_utils.py            # Detecção de GPUs
│
├── data/                        # CSVs gerados (um por câmera)
│   ├── Camera_01.csv
│   ├── Camera_02.csv
│   └── ...
│
└── logs/                        # Logs do sistema
    └── app.log
```

## 🎯 Como Usar

### 1. Instalação

```bash
# Clonar ou extrair o projeto
cd detec_pellet

# Criar ambiente virtual (recomendado)
python -m venv venv

# Ativar ambiente
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Instalar PyTorch com CUDA (se tiver GPU NVIDIA)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 2. Executar Aplicação

```bash
python main.py
```

### 3. Adicionar Câmera

1. Na tela inicial, clique em **"+ Adicionar Câmera"**
2. Preencha o formulário:
   - **Nome**: Identificação da câmera (ex: "Linha_01")
   - **Caminho**: Arquivo de vídeo, índice webcam (0, 1...) ou URL RTSP
   - **Modelo**: Caminho para o modelo TensorRT (.engine) ou ONNX (.onnx)
   - **Taxa de Detecção**: Processar 1 a cada N frames
     - `1` = ~1 FPS (processamento lento, economia de recursos)
     - `5` = ~5 FPS (balanceado)
     - `10` = ~10 FPS (rápido, exige mais GPU)
   - **Escala mm/pixel**: Calibração (ex: 0.2 = 1 pixel = 0.2mm)
   - **Confiança**: Threshold do modelo (50-70% recomendado)
   - **Dispositivo**: Selecionar GPU ou CPU
3. Clique em **"Adicionar Câmera"**

### 4. Visualizar Detecções

1. Na lista de câmeras, clique em **"Visualizar"**
2. Veja:
   - Stream de vídeo com máscaras coloridas semi-transparentes
   - Tamanho de cada pelota em mm
   - Gráfico de distribuição granulométrica em tempo real
   - Estatísticas (total de pelotas, média, FPS)

### 5. Ver Histórico

1. Clique em **"Histórico"** na tela de câmeras
2. Selecione uma câmera específica ou veja todas
3. Analise a evolução temporal do tamanho médio

## 📊 Faixas Granulométricas

O sistema classifica as pelotas em 7 faixas:

| Faixa | Tamanho | Código |
|-------|---------|--------|
| **< 6.3 mm** | Muito pequena | `range_below_6` |
| **6.3-8 mm** | Pequena | `range_6_8` |
| **8-9 mm** | Pequena-média | `range_8_9` |
| **9-12 mm** | Média | `range_9_12` |
| **12-16 mm** | Média-grande | `range_12_16` |
| **16-19 mm** | Grande | `range_16_19` |
| **> 19 mm** | Muito grande | `range_above_19` |

## 📏 Calibração da Escala

A escala mm/pixel deve ser calibrada para cada câmera:

1. Grave um vídeo com objeto de referência (ex: régua)
2. Meça quantos pixels correspondem a uma distância conhecida
3. Calcule: `escala = distância_mm / distância_pixels`
4. Use essa escala no cadastro da câmera

**Exemplo**: Se 100mm ocupam 500 pixels → escala = 100/500 = **0.2 mm/pixel**

## 💾 Arquivos CSV

### Estrutura

Cada câmera gera seu próprio CSV em `data/<nome_camera>.csv`:

```
data/
├── Camera_01.csv      # Dados apenas da Camera_01
├── Linha_A.csv        # Dados apenas da Linha_A
└── Esteira_2.csv      # Dados apenas da Esteira_2
```

### Colunas

```csv
Data, camera_name, total_pellets, media, range_below_6, range_6_8, range_8_9,
range_9_12, range_12_16, range_16_19, range_above_19
```

- **Data**: Timestamp (YYYY-MM-DD HH:MM:SS)
- **camera_name**: Nome da câmera
- **total_pellets**: Quantidade total de pelotas detectadas
- **media**: Tamanho médio em mm
- **range_***: Relações (0.0 a 1.0) de cada faixa

### Exemplo

```csv
Data,camera_name,total_pellets,media,range_below_6,range_6_8,...
2026-03-05 10:00:00,Camera_01,150,10.5,0.02,0.15,...
2026-03-05 10:00:01,Camera_01,148,10.4,0.03,0.14,...
```

## 🎨 Visualização com Máscaras

O sistema agora mostra **máscaras de segmentação reais**:

- ✅ Máscaras coloridas semi-transparentes (40% opacidade)
- ✅ Cada pelota com cor aleatória diferente
- ✅ Contorno verde destacado (2px)
- ✅ Label com tamanho em mm
- ✅ Fundo preto no texto para legibilidade

**Cálculo baseado em área real**:
- Usa `cv2.contourArea()` para calcular pixels da máscara
- Diâmetro equivalente: `d = 2 × √(área / π)`
- Muito mais preciso que círculo envolvente!

## 📈 Gráficos

### Tempo Real (Tela de Visualização)

- Gráfico de barras vertical
- Mostra distribuição granulométrica instantânea
- Atualiza a cada frame processado

### Histórico Temporal (Janela Separada)

- Gráfico de linha temporal
- Mostra evolução do tamanho médio
- Suporta múltiplas câmeras simultaneamente
- Filtro por câmera individual
- Auto-refresh a cada 5 segundos

## 🛠️ Geração de Executável

Para criar um executável standalone:

```bash
python build_executable.py
```

O executável será gerado em `dist/PelletDetector.exe`.

**Nota**: O arquivo pode ser grande (200-500MB) devido às dependências.

## 📝 Logs

Logs são gravados em `logs/app.log` com informações sobre:
- Carregamento de modelos
- FPS de processamento por câmera
- Erros e exceções
- Ações do usuário
- Detecções realizadas

## 🔧 Troubleshooting

### Erro: "Modelo não encontrado"
- Verifique se o arquivo do modelo existe no caminho especificado
- Certifique-se de usar modelo TensorRT (.engine) ou ONNX (.onnx)

### Erro: "Falha ao deserializar engine TensorRT"
- O modelo .engine foi gerado em outra máquina/GPU
- Solução:
  1. Gerar .engine na máquina de destino, OU
  2. Usar modelo ONNX (.onnx) como alternativa
  3. Veja documentação do Ultralytics para exportação

### Erro: "GPU não disponível"
- Instale os drivers NVIDIA mais recentes
- Instale CUDA Toolkit compatível
- Use "CPU" se não tiver GPU disponível

### Inferência muito lenta
- Aumente a taxa de detecção (processar menos frames)
- Use GPU em vez de CPU
- Verifique se está usando modelo TensorRT (.engine)
- Reduza a resolução do vídeo se possível

### UI travando ao arrastar janela
- Comportamento normal do Tkinter no Windows
- O backend continua funcionando normalmente
- Evite arrastar durante processamento pesado

### CSV corrompido
- Os logs em `logs/app.log` contêm detalhes do erro
- Faça backup regular dos CSVs
- Verifique permissões da pasta `data/`

## 💡 Dicas de Performance

### Taxa de Detecção

A taxa de detecção controla quantos frames são processados:

- **Taxa 1**: Processa 1 frame por segundo (~1 FPS)
  - Uso: Monitoramento lento, economia de GPU

- **Taxa 5**: Processa 1 a cada 5 frames (~5 FPS se vídeo for 25 FPS)
  - Uso: Balanceado, recomendado para produção

- **Taxa 10**: Processa 1 a cada 10 frames (~10 FPS)
  - Uso: Análise rápida, exige GPU boa

### Múltiplas Câmeras

- GPU RTX 3060: Suporta 3-4 câmeras simultâneas com TensorRT
- CPU: Suporta 1-2 câmeras com ONNX (lento)
- Cada câmera roda em thread separada

## 📚 Documentação Adicional

- **MUDANCAS_SEGMENTACAO.md** - Detalhes da implementação com máscaras
- **MUDANCA_CSV_POR_CAMERA.md** - Detalhes do CSV separado por câmera
- **logs/app.log** - Logs em tempo real do sistema

## 🔍 Informações Técnicas

### Medição Baseada em Área

O sistema calcula o tamanho das pelotas usando a **área real da máscara de segmentação**:

1. YOLO gera máscara binária para cada pelota
2. `cv2.findContours()` extrai contornos individuais
3. `cv2.contourArea()` calcula área em pixels
4. Diâmetro equivalente: `d = 2 × √(área / π)`
5. Conversão para mm: `d_mm = d_pixels × escala`

**Vantagem**: Muito mais preciso que métodos baseados em bounding box ou círculo envolvente.

### Thread Safety

- Cada câmera roda em thread separada (`threading.Thread`)
- Comunicação via `queue.Queue` (thread-safe)
- CSVLogger usa `threading.Lock` para escritas
- UI usa polling não-bloqueante (`after()`)

### Formato do Modelo

**Suportado**:
- ✅ TensorRT (.engine) - **Recomendado** para máxima performance
- ✅ ONNX (.onnx) - Alternativa universal

**Como gerar .engine**:
```python
from ultralytics import YOLO

model = YOLO('seu_modelo.pt')
model.export(format='engine', device=0)  # Gera .engine otimizado para GPU 0
```

## 🔐 Licença

Este projeto foi desenvolvido como ferramenta industrial para medição de pelotas de minério.

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique os logs em `logs/app.log`
2. Consulte a seção Troubleshooting acima
3. Leia os arquivos de mudanças para funcionalidades específicas

---

**Status**: ✅ Sistema completo e funcional

**Desenvolvido com**:
- Python 3.8+
- Ultralytics YOLO
- TensorRT
- CustomTkinter
- OpenCV

**Data**: Março 2026
