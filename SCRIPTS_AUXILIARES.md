# 🛠️ Scripts Auxiliares

Guia de scripts utilitários do projeto Pellet Detector.

## 📋 Visão Geral

| Script | Função | Quando Usar |
|--------|--------|-------------|
| **main.py** | Executar aplicação | Uso diário |
| **test_installation.py** | Testar instalação | Após instalar dependências |
| **test_tensorrt.py** | Testar modelo TensorRT | Validar modelo .engine |
| **conv.py** | Converter .pt para .engine | Gerar modelo otimizado |
| **build_executable.py** | Gerar executável .exe | Distribuição |
| **config.py** | Configurações globais | Ajustar parâmetros |

---

## 🚀 main.py

**Função**: Ponto de entrada principal da aplicação

### Como usar

```bash
python main.py
```

### O que faz

1. Configura logging
2. Inicializa aplicação UI
3. Abre interface CustomTkinter
4. Gerencia fechamento limpo

### Quando usar

- ✅ **Uso diário** - sempre que quiser usar o sistema
- ✅ Adicionar/visualizar câmeras
- ✅ Monitorar detecções em tempo real

---

## 🧪 test_installation.py

**Função**: Valida instalação de todas as dependências

### Como usar

```bash
python test_installation.py
```

### O que faz

1. Testa imports de todos os módulos
2. Verifica versões instaladas
3. Detecta GPUs NVIDIA disponíveis
4. Testa ONNX Runtime providers
5. Verifica CUDA (se GPU presente)
6. Testa PyTorch e Ultralytics

### Saída esperada

```
============================================================
Testando Instalação do Pellet Detector
============================================================
[OK] CustomTkinter
[OK] OpenCV
[OK] NumPy
[OK] Pandas
[OK] Matplotlib
[OK] Pillow
[OK] ONNX Runtime

============================================================
Verificando GPU
============================================================
[OK] 1 GPU(s) NVIDIA encontrada(s):
     GPU 0: NVIDIA GeForce RTX 3060 (12 GB)

[OK] ONNX Runtime Providers disponíveis: CUDAExecutionProvider, CPUExecutionProvider
     ✓ GPU habilitada via CUDA

[OK] PyTorch versão: 2.0.1
     ✓ CUDA disponível: True
     ✓ Dispositivo: cuda

[OK] Ultralytics instalado

============================================================
Resultado
============================================================
✅ Todas as dependências estão instaladas corretamente!
```

### Quando usar

- ✅ **Após instalar** requirements.txt
- ✅ Verificar se GPU está funcionando
- ✅ Diagnosticar problemas de instalação
- ✅ Antes de rodar aplicação pela primeira vez

---

## ⚡ test_tensorrt.py

**Função**: Testa carregamento e inferência do modelo TensorRT

### Como usar

```bash
python test_tensorrt.py
```

### O que faz

1. Verifica se modelo .engine existe
2. Carrega modelo via Ultralytics
3. Executa inferência de teste
4. Mede tempo de inferência
5. Faz benchmark (10 inferências)
6. Calcula FPS médio

### Saída esperada

```
============================================================
Teste TensorRT - RGB_960m_256.engine
============================================================
[OK] Modelo encontrado: RGB_960m_256.engine

[...] Carregando detector TensorRT...
[OK] Detector carregado com sucesso!

[...] Criando frame de teste (960x960)...
[...] Executando inferência...
[OK] Inferência OK!
  - Tempo: 12.34ms
  - Mask shape: (960, 960)
  - Mask min/max: 0/1

[...] Benchmark (10 inferências)...
[OK] Benchmark completo!
  - Tempo médio: 11.23ms
  - FPS: 89.0

============================================================
[SUCESSO] TESTE PASSOU! TensorRT funcionando!
============================================================
```

### Quando usar

- ✅ **Após gerar modelo .engine**
- ✅ Verificar se TensorRT está funcionando
- ✅ Medir performance da GPU
- ✅ Diagnosticar problemas de inferência
- ✅ Comparar performance entre GPUs

---

## 🔄 conv.py

**Função**: Converte modelo PyTorch (.pt) para TensorRT (.engine)

### Como usar

```bash
python conv.py
```

### Pré-requisitos

- Arquivo `RGB_960m_256.pt` no diretório raiz
- GPU NVIDIA disponível
- CUDA instalado
- Ultralytics instalado

### O que faz

1. Verifica se GPU está ativa
2. Remove .engine antigo (se existir)
3. Carrega modelo .pt
4. Exporta para formato TensorRT (.engine)
5. Valida arquivo gerado

### Saída esperada

```
--- Verificação de Ambiente ---
CUDA disponível: True
GPU detectada: NVIDIA GeForce RTX 3060

--- Iniciando Exportação (Isso pode demorar uns minutos) ---
[Ultralytics logs...]

--- Finalizado ---
SUCESSO: Novo arquivo gerado em: C:\Projects\SAM\detec_pellet - Copia\RGB_960m_256.engine
```

### Parâmetros de exportação

```python
model.export(
    format='engine',  # Formato TensorRT
    device=0,         # GPU 0
    half=True,        # FP16 (mais rápido)
    simplify=True     # Otimizações extras
)
```

### Quando usar

- ✅ **Primeira vez** - gerar .engine do .pt
- ✅ Trocar de GPU (regenerar .engine)
- ✅ Atualizar modelo PyTorch
- ✅ Otimizar para máquina específica

### ⚠️ Importante

- O .engine é **específico para a GPU** que o gerou
- Trocar de máquina = regenerar .engine
- Processo demora 2-5 minutos

---

## 📦 build_executable.py

**Função**: Gera executável standalone (.exe) com PyInstaller

### Como usar

```bash
python build_executable.py
```

### O que faz

1. Configura PyInstaller com parâmetros adequados
2. Inclui modelo .engine
3. Coleta temas CustomTkinter
4. Adiciona hidden imports necessários
5. Gera executável em `dist/PelletDetector.exe`

### Saída esperada

```
[PyInstaller logs...]

Executável gerado com sucesso!
Localização: dist/PelletDetector.exe
Tamanho: ~300MB

Próximos passos:
1. Testar: dist\PelletDetector.exe
2. Distribuir: Copiar dist/PelletDetector.exe + RGB_960m_256.engine
```

### Configuração atual

```python
PyInstaller.__main__.run([
    'main.py',
    '--name=PelletDetector',
    '--onefile',                      # Arquivo único
    '--windowed',                     # Sem console
    '--add-data=RGB_960m_256.engine;.',  # Incluir modelo
    '--collect-all=customtkinter',    # Temas
    '--hidden-import=ultralytics',
    '--hidden-import=torch',
])
```

### Quando usar

- ✅ **Distribuição** - dar para outras pessoas
- ✅ Executar sem Python instalado
- ✅ Ambiente de produção
- ✅ Deploy em máquinas sem dev env

### ⚠️ Limitações

- Executável grande (200-500MB)
- Pode demorar 5-10 minutos para gerar
- Modelo .engine deve estar incluído

---

## ⚙️ config.py

**Função**: Configurações globais centralizadas

### O que contém

#### 1. Caminhos
```python
MODEL_PATH = 'RGB_960m_256.engine'
DATA_DIR = 'data/'
LOGS_DIR = 'logs/'
CSV_PATH = 'data/detections.csv'
```

#### 2. Faixas Granulométricas
```python
GRANULOMETRIC_RANGES = {
    'range_below_6': (0, 6.3),
    'range_6_8': (6.3, 8.0),
    # ... 7 faixas no total
}
```

#### 3. Defaults do Sistema
```python
DEFAULT_CONFIDENCE = 0.5         # 50%
DEFAULT_DETECTION_RATE = 5       # 1 a cada 5 frames
DEFAULT_SCALE_MM_PIXEL = 0.1     # 0.1 mm/pixel
DEFAULT_MODEL_INPUT_SIZE = (960, 960)
```

#### 4. Configurações de UI
```python
UI_UPDATE_INTERVAL = 30          # 30ms (atualizar vídeo)
HISTORY_UPDATE_INTERVAL = 5000   # 5s (atualizar histórico)
MAX_QUEUE_SIZE = 10              # Tamanho da fila de frames
```

### Quando modificar

- ⚠️ **Raramente** - só se precisar mudar defaults
- ✅ Adicionar nova faixa granulométrica
- ✅ Ajustar intervalos de UI
- ✅ Mudar caminhos padrão

### Como modificar faixas

1. Editar `GRANULOMETRIC_RANGES`
2. Atualizar `RANGE_ORDER`
3. Atualizar `RANGE_LABELS`
4. Adicionar coluna em `CSV_COLUMNS`

**Exemplo** - adicionar faixa 19-25mm:

```python
GRANULOMETRIC_RANGES = {
    # ... faixas existentes ...
    'range_19_25': (19.0, 25.0),  # NOVA
    'range_above_25': (25.0, float('inf'))  # Renomear
}

RANGE_ORDER.append('range_19_25')

RANGE_LABELS['range_19_25'] = '19-25 mm'

CSV_COLUMNS.append('range_19_25')
```

---

## 📊 Resumo de Uso

### Fluxo Típico

```bash
# 1. Instalar (primeira vez)
pip install -r requirements.txt
python test_installation.py

# 2. Converter modelo (primeira vez)
python conv.py
python test_tensorrt.py

# 3. Usar diariamente
python main.py

# 4. Distribuir (opcional)
python build_executable.py
```

### Diagnóstico de Problemas

```bash
# Problema: Instalação
python test_installation.py

# Problema: Modelo
python test_tensorrt.py

# Problema: GPU
python test_installation.py  # Verificar seção GPU
```

### Manutenção

```bash
# Atualizar modelo
python conv.py              # Regenerar .engine

# Testar mudanças
python test_tensorrt.py     # Validar modelo
python main.py              # Testar aplicação
```

---

## 🔍 Dependências entre Scripts

```
test_installation.py
  └─> Não depende de nada
       (pode rodar imediatamente após pip install)

conv.py
  └─> Precisa de: RGB_960m_256.pt
       Gera: RGB_960m_256.engine

test_tensorrt.py
  └─> Precisa de: RGB_960m_256.engine
       (gerado por conv.py)

main.py
  └─> Precisa de: RGB_960m_256.engine
       (gerado por conv.py)

build_executable.py
  └─> Precisa de: main.py + todas dependências
       Gera: dist/PelletDetector.exe
```

---

## 📝 Logs e Outputs

| Script | Gera Logs? | Onde? |
|--------|------------|-------|
| **test_installation.py** | ❌ Não | Console apenas |
| **test_tensorrt.py** | ❌ Não | Console apenas |
| **conv.py** | ❌ Não | Console apenas |
| **main.py** | ✅ Sim | `logs/app.log` |
| **build_executable.py** | ⚠️ Parcial | Console + build/ |

---

## ⚠️ Avisos Importantes

### conv.py
- **Demora**: 2-5 minutos para converter
- **GPU específica**: .engine não é portável
- **Backup**: Guardar .pt original

### test_tensorrt.py
- **Requer .engine**: Rodar conv.py antes
- **Benchmark**: Fecha outras aplicações GPU

### build_executable.py
- **Grande**: ~300-500MB
- **Demorado**: 5-10 minutos
- **Testar**: Sempre testar .exe antes de distribuir

---

## 📞 Suporte Rápido

| Erro | Script | Solução |
|------|--------|---------|
| "Module not found" | test_installation.py | `pip install -r requirements.txt` |
| "Modelo não encontrado" | test_tensorrt.py | Rodar `conv.py` primeiro |
| "CUDA not available" | test_installation.py | Instalar drivers NVIDIA |
| ".engine deserialize error" | test_tensorrt.py | Regenerar com `conv.py` |
| "PyInstaller failed" | build_executable.py | Verificar dependências |

---

**Última atualização**: Março 2026
**Status**: ✅ Documentação completa
