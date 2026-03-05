# Primeiros Passos - Pellet Detector

## ✅ ÓTIMA NOTÍCIA: Seu Modelo Está Pronto!

Você tem o modelo `RGB_960m_256.engine` (formato TensorRT) - **o melhor formato possível!**

TensorRT é **5-10x mais rápido** que ONNX e está totalmente suportado pelo sistema.

## Instalação Rápida (Recomendado)

### Windows

```bash
# 1. Ativar ambiente virtual
venv\Scripts\activate

# 2. Instalar dependências base
pip install -r requirements.txt

# 3. Instalar TensorRT
pip install nvidia-tensorrt

# 4. Instalar PyCUDA
pip install pycuda

# 5. Pronto! Executar
python main.py
```

**Veja `TENSORRT_SETUP.md` para detalhes completos.**

## ⚡ Alternativa: Usar ONNX (Fallback)

Se tiver problemas com TensorRT, o sistema também suporta ONNX:

### Opção ONNX: Converter .engine para .onnx

Se você tiver o modelo original em PyTorch (.pt ou .pth):

```python
import torch
import torch.onnx

# Carregar modelo PyTorch
model = torch.load('seu_modelo.pt')
model.eval()

# Dummy input (ajuste para o tamanho correto)
dummy_input = torch.randn(1, 3, 960, 960)

# Exportar para ONNX
torch.onnx.export(
    model,
    dummy_input,
    'RGB_960m_256.onnx',
    export_params=True,
    opset_version=11,
    do_constant_folding=True,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
)
```

### Opção 2: Implementar TensorRT (Avançado)

O código em `core/detector.py` tem um placeholder para TensorRT. Para implementar:

1. Instale NVIDIA TensorRT:
   ```bash
   pip install nvidia-tensorrt
   pip install pycuda
   ```

2. Implemente `_load_engine()` em `core/detector.py`:
   ```python
   import tensorrt as trt
   import pycuda.driver as cuda
   import pycuda.autoinit

   def _load_engine(self):
       # Carregar engine
       with open(self.model_path, 'rb') as f, trt.Runtime(trt.Logger(trt.Logger.WARNING)) as runtime:
           self.engine = runtime.deserialize_cuda_engine(f.read())
       # ... resto da implementação
   ```

## Instalação e Configuração

### 1. Instalar Dependências

```bash
# Ativar ambiente virtual
venv\Scripts\activate

# Instalar pacotes
pip install -r requirements.txt

# Se tiver GPU NVIDIA
pip install onnxruntime-gpu
```

### 2. Preparar Modelo

```bash
# Renomear ou converter para ONNX
# Se já tiver .onnx:
# RGB_960m_256.onnx -> deve estar no diretório raiz
```

### 3. Testar GPU (Opcional)

```python
# Testar detecção de GPU
python -c "from utils.gpu_utils import list_nvidia_gpus; print(list_nvidia_gpus())"

# Testar ONNX Runtime GPU
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

### 4. Executar Aplicação

```bash
python main.py
```

## Calibração Inicial

Antes de usar em produção, faça a calibração da escala:

1. **Grave vídeo de referência**: Filme pelotas com uma régua visível

2. **Meça em pixels**: Use um editor de imagem para medir o diâmetro de uma pelota conhecida

3. **Calcule escala**:
   ```
   Exemplo:
   - Pelota real: 12mm
   - Pelota na imagem: 60 pixels
   - Escala = 12 / 60 = 0.2 mm/pixel
   ```

4. **Use no cadastro**: Insira esse valor no campo "Escala mm/pixel"

## Teste Rápido

Para testar o sistema rapidamente:

### Criar vídeo de teste (se não tiver)

Use qualquer vídeo MP4 ou:

```python
# Gerar vídeo de teste com círculos (simula pelotas)
import cv2
import numpy as np

out = cv2.VideoWriter('teste.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 30, (640, 480))

for i in range(300):  # 10 segundos a 30fps
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Desenhar círculos aleatórios
    for _ in range(10):
        x = np.random.randint(50, 590)
        y = np.random.randint(50, 430)
        r = np.random.randint(20, 50)
        cv2.circle(frame, (x, y), r, (255, 255, 255), -1)

    out.write(frame)

out.release()
print("Vídeo de teste criado: teste.mp4")
```

### Adicionar câmera de teste

1. Execute `python main.py`
2. Clique em "Adicionar Câmera"
3. Preencha:
   - Nome: "Teste"
   - Caminho: "teste.mp4"
   - Modelo: (seu modelo .onnx)
   - Taxa: 5
   - Escala: 0.2
   - Confiança: 50
   - Dispositivo: GPU 0 ou CPU
4. Clique "Adicionar"

## Estrutura de Arquivos Gerados

Após executar, serão criados:

```
data/
└── detections.csv          # Dados de todas as detecções

logs/
└── app.log                 # Logs do sistema
```

## Próximos Passos

1. **Teste com vídeo real**: Use um vídeo de produção
2. **Ajuste parâmetros**: Taxa de detecção, confiança, escala
3. **Valide medições**: Compare com medições manuais
4. **Configure múltiplas câmeras**: Se necessário
5. **Gere executável**: `python build_executable.py`

## Troubleshooting

### "No module named 'onnxruntime'"
```bash
pip install onnxruntime-gpu  # Para GPU
# ou
pip install onnxruntime      # Para CPU
```

### "Modelo não encontrado"
- Verifique se o arquivo .onnx está no diretório raiz
- Ou especifique o caminho completo no cadastro

### "CUDA Provider not available"
- Instale `onnxruntime-gpu`
- Verifique drivers NVIDIA atualizados
- Use CPU como alternativa

### GPU não aparece na lista
- Execute: `nvidia-smi` no terminal
- Se não funcionar, drivers não estão instalados
- Instale drivers NVIDIA mais recentes

## Suporte

Verifique sempre os logs em `logs/app.log` para diagnóstico de problemas.
