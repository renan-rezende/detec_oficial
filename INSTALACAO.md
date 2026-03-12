# 📦 Guia de Instalação - Pellet Detector

Guia completo para configurar e executar o sistema de detecção de pelotas.

## 📋 Pré-requisitos

### Hardware Mínimo

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| **CPU** | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7 |
| **RAM** | 8 GB | 16 GB ou mais |
| **GPU** | CPU only (lento) | NVIDIA RTX 2060+ |
| **Armazenamento** | 5 GB livres | 10 GB+ (para CSVs) |

### Software Necessário

1. **Python 3.8 ou superior**
   - Download: https://www.python.org/downloads/
   - ⚠️ Marque "Add Python to PATH" durante instalação

2. **CUDA Toolkit** (apenas se tiver GPU NVIDIA)
   - CUDA 11.x ou 12.x
   - Download: https://developer.nvidia.com/cuda-downloads

3. **Drivers NVIDIA** (apenas para GPU)
   - Versão mais recente
   - Download: https://www.nvidia.com/drivers

## 🚀 Instalação Passo a Passo

### 1. Preparar Ambiente

```bash
# Navegar até o diretório do projeto
cd C:\Projects\SAM\detec_pellet - Copia

# Criar ambiente virtual (recomendado)
python -m venv venv

# Ativar ambiente virtual
# No Windows:
venv\Scripts\activate

# No Linux/Mac:
source venv/bin/activate
```

### 2. Instalar Dependências Base

```bash
# Atualizar pip
python -m pip install --upgrade pip

# Instalar dependências
pip install -r requirements.txt
```

### 3. Instalar PyTorch (GPU ou CPU)

#### Opção A: Com GPU NVIDIA (Recomendado)

```bash
# CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

#### Opção B: Apenas CPU (Mais Lento)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Verificar Instalação

```bash
# Testar se está tudo OK
python test_installation.py
```

**Saída esperada**:
```
✓ Python: 3.10.x
✓ OpenCV: 4.8.x
✓ NumPy: 1.24.x
✓ Pandas: 2.0.x
✓ CustomTkinter: 5.2.x
✓ Ultralytics: 8.x.x
✓ PyTorch: 2.x.x
✓ GPU NVIDIA detectada: NVIDIA GeForce RTX 3060
✓ CUDA disponível: 12.1
✓ Todas dependências instaladas corretamente!
```

## 🔧 Solução de Problemas na Instalação

### Erro: "pip não reconhecido"

**Causa**: Python não está no PATH

**Solução**:
1. Reinstalar Python marcando "Add Python to PATH"
2. OU adicionar manualmente ao PATH:
   - Windows: `C:\Python310\Scripts\` e `C:\Python310\`

### Erro ao instalar PyTorch

**Causa**: Versão de CUDA incompatível

**Solução**:
```bash
# Verificar versão do CUDA instalada
nvcc --version

# Instalar PyTorch compatível:
# CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# CPU only
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Erro: "CUDA not available"

**Verificações**:
```python
import torch
print(torch.cuda.is_available())  # Deve ser True
print(torch.cuda.get_device_name(0))  # Nome da GPU
```

**Se retornar False**:
1. Verificar drivers NVIDIA atualizados
2. Verificar CUDA Toolkit instalado
3. Reinstalar PyTorch com versão CUDA correta

### Erro: "Microsoft Visual C++ required"

**Causa**: Faltam bibliotecas C++ no Windows

**Solução**:
1. Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
2. Instalar e reiniciar

### Erro ao importar cv2 (OpenCV)

**Solução**:
```bash
pip uninstall opencv-python opencv-contrib-python
pip install opencv-python==4.8.0
```

## 📁 Estrutura Após Instalação

```
detec_pellet/
├── venv/                    # Ambiente virtual (criado)
├── data/                    # Será criado automaticamente
├── logs/                    # Será criado automaticamente
├── main.py
├── config.py
├── requirements.txt
├── RGB_960m_256.engine     # Seu modelo
└── ...
```

## 🎯 Preparar Modelo

### Se você tem modelo .pt (PyTorch)

```python
from ultralytics import YOLO

# Carregar modelo
model = YOLO('seu_modelo.pt')

# Exportar para TensorRT (GPU)
model.export(format='engine', device=0)

# OU exportar para ONNX (universal)
model.export(format='onnx')
```

### Se você já tem .engine

✅ **Pronto para usar!**
- Certifique-se que foi gerado na mesma máquina/GPU
- Ou regenere usando o código acima

## ▶️ Primeira Execução

```bash
# Ativar ambiente (se não estiver ativo)
venv\Scripts\activate

# Executar aplicação
python main.py
```

**Interface deve abrir automaticamente!**

## 🧪 Testar com Webcam

1. Executar `python main.py`
2. Clicar em "+ Adicionar Câmera"
3. Preencher:
   - Nome: `Teste_Webcam`
   - Caminho: `0` (primeira webcam)
   - Modelo: `RGB_960m_256.engine`
   - Taxa: `5`
   - Escala: `0.2`
   - Confiança: `50`
   - Device: Selecionar GPU 0 ou CPU
4. Clicar "Adicionar Câmera"
5. Clicar "Visualizar"

## 🎥 Testar com Vídeo

```bash
# Mesmos passos, mas no campo "Caminho":
# Usar caminho completo do vídeo
C:\Videos\pelotas_teste.mp4
```

## 📊 Verificar Resultados

### CSVs Gerados

```bash
# Ver CSVs criados
dir data\*.csv

# Exemplo de saída:
# data/Teste_Webcam.csv
# data/Camera_01.csv
```

### Logs

```bash
# Ver logs
type logs\app.log

# Ou abrir no Notepad
notepad logs\app.log
```

## 🔍 Verificação Final

### Checklist Pós-Instalação

- [ ] Python 3.8+ instalado
- [ ] Ambiente virtual criado e ativado
- [ ] Todas dependências instaladas (requirements.txt)
- [ ] PyTorch instalado com CUDA (se GPU)
- [ ] `test_installation.py` passou sem erros
- [ ] GPU detectada (se aplicável)
- [ ] Modelo TensorRT ou ONNX disponível
- [ ] `python main.py` abre a interface
- [ ] Pasta `data/` existe
- [ ] Pasta `logs/` existe

## 📈 Próximos Passos

1. **Calibrar Escala**
   - Gravar vídeo com régua
   - Calcular mm/pixel
   - Ver seção "Calibração da Escala" no README.md

2. **Testar com Dados Reais**
   - Adicionar câmera com vídeo de produção
   - Ajustar confiança e taxa de detecção
   - Verificar precisão das medições

3. **Monitorar Performance**
   - Verificar FPS nos logs
   - Ajustar taxa de detecção se necessário
   - Considerar usar taxa maior para economia de GPU

4. **Exportar Dados**
   - CSVs em `data/<nome_camera>.csv`
   - Abrir no Excel para análise
   - Importar em sistema de BI se necessário

## 🏭 Deploy em Produção

Para deploy em servidor industrial sem internet, consulte **[PRODUCAO.md](PRODUCAO.md)**.

Resumo rápido:
1. `python build_executable.py` → gera `dist/PelletDetector/` (pasta, não .exe único)
2. Copiar `dist/PelletDetector/` + `RGB_960m_256.pt` + `conv.py` para o servidor
3. No servidor: `python conv.py` → gera o `.engine` otimizado para a GPU local
4. Mover o `.engine` para dentro de `dist/PelletDetector/`
5. Executar `PelletDetector.exe`

## 🛠️ Manutenção

### Atualizar Dependências

```bash
# Atualizar pip
python -m pip install --upgrade pip

# Atualizar pacotes
pip install --upgrade -r requirements.txt
```

### Limpar Cache

```bash
# Remover arquivos compilados Python
rmdir /s /q __pycache__
rmdir /s /q core\__pycache__
rmdir /s /q ui\__pycache__
rmdir /s /q utils\__pycache__
```

### Backup de Dados

```bash
# Fazer backup dos CSVs
xcopy data\*.csv backup\data\ /Y

# Fazer backup dos logs
xcopy logs\*.log backup\logs\ /Y
```

## 📞 Suporte

Se encontrar problemas:

1. **Verificar logs**: `logs/app.log`
2. **Verificar instalação**: `python test_installation.py`
3. **Consultar troubleshooting**: Ver README.md seção "Troubleshooting"
4. **Recriar ambiente**:
   ```bash
   rmdir /s /q venv
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

---

**Status**: Guia de instalação completo

**Tempo estimado**: 15-30 minutos

**Dificuldade**: Fácil (seguindo os passos)
