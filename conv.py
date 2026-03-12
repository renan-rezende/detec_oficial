"""
Script para compilar o modelo .pt para .engine (TensorRT)
Execute este script NO SERVIDOR DE PRODUCAO, nao na maquina de desenvolvimento.

O arquivo .engine e especifico para a GPU e versao de TensorRT da maquina onde e gerado.
"""
from ultralytics import YOLO
import torch
import os
import sys

# Resolve caminhos relativos ao diretório deste script (funciona em qualquer máquina)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
path_pt = os.path.join(BASE_DIR, 'RGB_960m_256.pt')
path_engine = os.path.join(BASE_DIR, 'RGB_960m_256.engine')

# Verificação de ambiente
print("--- Verificação de Ambiente ---")
print(f"Diretório: {BASE_DIR}")
print(f"CUDA disponível: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("ERRO: GPU não detectada! Verifique driver NVIDIA e CUDA.")
    sys.exit(1)

print(f"GPU detectada: {torch.cuda.get_device_name(0)}")

# Verificar se modelo .pt existe
if not os.path.exists(path_pt):
    print(f"ERRO: Modelo .pt não encontrado em: {path_pt}")
    print("Coloque o arquivo RGB_960m_256.pt no mesmo diretório deste script.")
    sys.exit(1)

# Remove engine antigo para garantir recompilação limpa
if os.path.exists(path_engine):
    os.remove(path_engine)
    print("Arquivo .engine antigo removido.")

# Exportar para TensorRT
print()
print("--- Iniciando Exportação TensorRT (pode demorar alguns minutos) ---")
model = YOLO(path_pt, task='segment')
model.export(format='engine', device=0, half=True, simplify=True)

print()
print("--- Finalizado ---")
if os.path.exists(path_engine):
    print(f"SUCESSO: Novo .engine gerado em: {path_engine}")
else:
    print("ERRO: O arquivo .engine não foi gerado. Verifique os logs acima.")
    sys.exit(1)
