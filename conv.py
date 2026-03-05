from ultralytics import YOLO
import torch
import os

# 1. Verifica se a GPU está realmente ativa
print(f"--- Verificação de Ambiente ---")
print(f"CUDA disponível: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("ERRO: Sua GPU não foi detectada! Verifique a instalação do driver.")
    exit()
print(f"GPU detectada: {torch.cuda.get_device_name(0)}")

# 2. Caminhos (Use caminhos brutos para não ter erro)
path_pt = r'C:\Projects\SAM\detec_pellet - Copia\RGB_960m_256.pt'
path_engine = r'C:\Projects\SAM\detec_pellet - Copia\RGB_960m_256.engine'

# Remove o engine antigo se ele ainda existir por algum motivo
if os.path.exists(path_engine):
    os.remove(path_engine)
    print(f"Arquivo antigo removido.")

# 3. Carrega e Exporta
print(f"--- Iniciando Exportação (Isso pode demorar uns minutos) ---")
model = YOLO(path_pt, task='segment')
# O format='engine' vai criar o arquivo .engine na mesma pasta do .pt
model.export(format='engine', device=0, half=True, simplify=True)

print(f"--- Finalizado ---")
if os.path.exists(path_engine):
    print(f"SUCESSO: Novo arquivo gerado em: {path_engine}")
else:
    print("ERRO: O arquivo .engine não foi gerado. Verifique os logs acima.")