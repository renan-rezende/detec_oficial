"""
Teste rapido do TensorRT com seu modelo
"""
import sys
import os
import numpy as np
import cv2

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.detector import Detector
from utils.logger import setup_logger

logger = setup_logger()

def test_tensorrt():
    """Testa carregamento e inferencia do modelo TensorRT"""

    print("="*60)
    print("Teste TensorRT - RGB_960m_256.engine")
    print("="*60)

    # Verificar se modelo existe
    model_path = "RGB_960m_256.engine"

    if not os.path.exists(model_path):
        print(f"[ERRO] Modelo nao encontrado: {model_path}")
        return False

    print(f"[OK] Modelo encontrado: {model_path}")

    try:
        # Carregar detector
        print("\n[...] Carregando detector TensorRT...")
        detector = Detector(
            model_path=model_path,
            device='cuda:0',
            confidence=0.5
        )
        print("[OK] Detector carregado com sucesso!")

        # Criar frame de teste
        print("\n[...] Criando frame de teste (960x960)...")
        test_frame = np.random.randint(0, 255, (960, 960, 3), dtype=np.uint8)

        # Executar inferencia
        print("[...] Executando inferencia...")
        mask, inference_time = detector.infer(test_frame)

        print(f"[OK] Inferencia OK!")
        print(f"  - Tempo: {inference_time:.2f}ms")
        print(f"  - Mask shape: {mask.shape}")
        print(f"  - Mask min/max: {mask.min()}/{mask.max()}")

        # Benchmark
        print("\n[...] Benchmark (10 inferencias)...")
        times = []
        for i in range(10):
            _, t = detector.infer(test_frame)
            times.append(t)

        avg_time = np.mean(times)
        fps = 1000.0 / avg_time

        print(f"[OK] Benchmark completo!")
        print(f"  - Tempo medio: {avg_time:.2f}ms")
        print(f"  - FPS: {fps:.1f}")

        print("\n" + "="*60)
        print("[SUCESSO] TESTE PASSOU! TensorRT funcionando!")
        print("="*60)

        return True

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tensorrt()
    sys.exit(0 if success else 1)
