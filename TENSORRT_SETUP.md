# 🚀 Configuração TensorRT - Máxima Performance

## Por que TensorRT?

✅ **5-10x mais rápido** que ONNX Runtime
✅ **Latência ultra-baixa** (crítico para tempo real)
✅ **Uso otimizado de GPU** NVIDIA
✅ **Suporte nativo a FP16** (ainda mais rápido)

## Comparação de Performance

| Método | FPS Típico (RTX 3060) | Latência |
|--------|----------------------|----------|
| TensorRT FP32 | 60-100 FPS | ~10-15ms |
| TensorRT FP16 | 100-150 FPS | ~6-10ms |
| ONNX Runtime GPU | 15-30 FPS | ~30-60ms |
| ONNX Runtime CPU | 1-5 FPS | ~200-500ms |

## ✅ Seu Modelo Está Pronto!

Você já tem `RGB_960m_256.engine` - **está pronto para usar diretamente!**

## Instalação TensorRT

### Windows

#### 1. Instalar CUDA Toolkit

```bash
# Baixar CUDA 11.8 ou 12.x
# https://developer.nvidia.com/cuda-downloads
```

#### 2. Instalar cuDNN

```bash
# Baixar cuDNN compatível com sua versão CUDA
# https://developer.nvidia.com/cudnn
```

#### 3. Instalar TensorRT

```bash
# Opção 1: Via pip (recomendado)
pip install nvidia-tensorrt

# Opção 2: Download manual
# https://developer.nvidia.com/tensorrt
```

#### 4. Instalar PyCUDA

```bash
pip install pycuda
```

### Linux

```bash
# Ubuntu/Debian
# 1. CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
sudo dpkg -i cuda-keyring_1.0-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda

# 2. TensorRT
sudo apt-get install tensorrt

# 3. Python bindings
pip install nvidia-tensorrt pycuda
```

## Verificação da Instalação

```python
# Testar TensorRT
python -c "import tensorrt as trt; print(f'TensorRT {trt.__version__}')"

# Testar PyCUDA
python -c "import pycuda.driver as cuda; import pycuda.autoinit; print('PyCUDA OK')"

# Testar sistema completo
python test_installation.py
```

## Usar Seu Modelo .engine

Seu modelo `RGB_960m_256.engine` já funciona! Apenas use no cadastro da câmera:

```
1. Execute: python main.py
2. Adicionar Câmera
3. Caminho do Modelo: RGB_960m_256.engine
4. Device: GPU 0
5. Adicionar
```

O sistema detectará automaticamente que é TensorRT e usará a inferência otimizada.

## Conversão PyTorch → TensorRT (Referência)

Se você tiver o modelo PyTorch original e quiser recriar o .engine:

```python
import torch
import torch.onnx
from torch2trt import torch2trt

# 1. Carregar modelo PyTorch
model = torch.load('seu_modelo.pt')
model = model.cuda().eval()

# 2. Criar input dummy
x = torch.ones((1, 3, 960, 960)).cuda()

# 3. Converter para TensorRT
model_trt = torch2trt(
    model,
    [x],
    fp16_mode=False,  # True para FP16 (mais rápido)
    max_workspace_size=1 << 30,  # 1GB
    max_batch_size=1
)

# 4. Salvar engine
torch.save(model_trt.state_dict(), 'model.engine')
```

### Método Alternativo (trtexec)

```bash
# Via ONNX intermediário
# 1. PyTorch → ONNX
python -c "
import torch
model = torch.load('model.pt')
model.eval()
dummy = torch.randn(1, 3, 960, 960)
torch.onnx.export(model, dummy, 'model.onnx')
"

# 2. ONNX → TensorRT
trtexec --onnx=model.onnx \
        --saveEngine=model.engine \
        --explicitBatch \
        --fp16 \
        --workspace=2048
```

## Otimizações Avançadas

### FP16 (Half Precision)

```bash
# Reconverter com FP16 (2x mais rápido)
trtexec --onnx=model.onnx \
        --saveEngine=model_fp16.engine \
        --fp16 \
        --workspace=4096
```

### Múltiplas GPUs

No cadastro da câmera, selecione:
- GPU 0 para primeira câmera
- GPU 1 para segunda câmera
- etc.

## Troubleshooting

### Erro: "Could not load dynamic library 'nvinfer'"

```bash
# Windows: Adicionar ao PATH
# C:\Program Files\NVIDIA GPU Computing Toolkit\TensorRT\lib

# Linux
export LD_LIBRARY_PATH=/usr/local/lib/python3.x/dist-packages/tensorrt:$LD_LIBRARY_PATH
```

### Erro: "pycuda._driver.LogicError: cuInit failed: no device"

```bash
# Verificar drivers NVIDIA
nvidia-smi

# Se não funcionar, reinstalar drivers:
# https://www.nvidia.com/Download/index.aspx
```

### Erro: "Engine was built with a different version"

Seu .engine foi compilado para uma versão específica de TensorRT. Opções:

1. **Usar mesma versão TensorRT** do build
2. **Recompilar engine** com sua versão atual

### Performance não melhorou

Checklist:
- [ ] GPU está sendo usada? (verificar logs)
- [ ] Drivers NVIDIA atualizados?
- [ ] TensorRT instalado corretamente?
- [ ] Modelo é .engine e não .onnx?
- [ ] Testou FP16 mode?

## Benchmark

Para medir FPS real:

```bash
# O sistema automaticamente mostra FPS nos logs
python main.py

# Observe os logs a cada 5 segundos:
# [INFO] [Camera Name] FPS: 85.3, Inferência: 11.7ms
```

## Comparação: TensorRT vs ONNX

### Quando usar TensorRT (.engine):
✅ Produção industrial
✅ GPUs NVIDIA disponíveis
✅ Necessita máxima performance
✅ Mesmo ambiente de deploy

### Quando usar ONNX (.onnx):
✅ Desenvolvimento/testes
✅ Múltiplas plataformas
✅ GPU não-NVIDIA (Intel, AMD)
✅ Deploy em ambientes variados

## Performance Esperada

Com `RGB_960m_256.engine` em RTX 3060:

- **TensorRT FP32**: ~60-80 FPS (~12-16ms por frame)
- **TensorRT FP16**: ~100-120 FPS (~8-10ms por frame)

Isso significa que **cada câmera pode processar 60-120 frames por segundo** (muito além das necessidades industriais típicas de 10-30 FPS).

## Dica: Taxa de Detecção

Com TensorRT, você pode:

```
Taxa de detecção = 1
```

Processar **TODOS os frames** sem perda de performance (30 FPS → 30 detecções/seg).

Com ONNX, use:

```
Taxa de detecção = 5-10
```

Para manter FPS aceitável.

## Suporte

Verifique sempre:
1. `logs/app.log` - Mensagens do TensorRT
2. `nvidia-smi` - Status da GPU
3. Logs mostrarão: "TensorRT inicializado com sucesso (GPU acelerada)"

---

**Conclusão**: Seu modelo .engine está pronto! Apenas instale TensorRT e PyCUDA, e terá performance máxima.
