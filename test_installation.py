"""
Script de teste para validar instalação do Pellet Detector
"""
import sys

def test_imports():
    """Testa imports de todas dependências"""
    print("="*60)
    print("Testando Instalação do Pellet Detector")
    print("="*60)

    results = {}

    # Testar imports principais
    modules = [
        ('customtkinter', 'CustomTkinter'),
        ('cv2', 'OpenCV'),
        ('numpy', 'NumPy'),
        ('pandas', 'Pandas'),
        ('matplotlib', 'Matplotlib'),
        ('PIL', 'Pillow'),
        ('onnxruntime', 'ONNX Runtime'),
    ]

    for module_name, display_name in modules:
        try:
            __import__(module_name)
            results[display_name] = '✓ OK'
            print(f"[OK] {display_name}")
        except ImportError as e:
            results[display_name] = f'✗ ERRO: {e}'
            print(f"[ERRO] {display_name}: {e}")

    print("\n" + "="*60)
    print("Verificando GPU")
    print("="*60)

    # Testar GPU
    try:
        from utils.gpu_utils import list_nvidia_gpus
        gpus = list_nvidia_gpus()

        if gpus:
            print(f"[OK] {len(gpus)} GPU(s) NVIDIA encontrada(s):")
            for gpu in gpus:
                print(f"     GPU {gpu['id']}: {gpu['name']} ({gpu['memory']})")
        else:
            print("[AVISO] Nenhuma GPU NVIDIA encontrada. Usando CPU.")

    except Exception as e:
        print(f"[ERRO] Erro ao detectar GPU: {e}")

    # Testar ONNX Runtime providers
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        print(f"\n[OK] ONNX Runtime Providers disponíveis: {', '.join(providers)}")

        if 'CUDAExecutionProvider' in providers:
            print("     ✓ GPU habilitada via CUDA")
        else:
            print("     ! GPU não disponível, usando CPU")

    except Exception as e:
        print(f"[ERRO] Erro ao verificar ONNX Runtime: {e}")

    print("\n" + "="*60)
    print("Verificando Estrutura do Projeto")
    print("="*60)

    import os

    # Verificar diretórios
    dirs = ['core', 'ui', 'utils', 'data', 'logs']
    for dir_name in dirs:
        if os.path.exists(dir_name):
            print(f"[OK] Diretório '{dir_name}' existe")
        else:
            print(f"[ERRO] Diretório '{dir_name}' não encontrado")

    # Verificar arquivos principais
    files = ['config.py', 'main.py', 'requirements.txt']
    for file_name in files:
        if os.path.exists(file_name):
            print(f"[OK] Arquivo '{file_name}' existe")
        else:
            print(f"[ERRO] Arquivo '{file_name}' não encontrado")

    # Verificar modelo
    if os.path.exists('RGB_960m_256.engine'):
        print("[AVISO] Modelo .engine encontrado. Converta para .onnx para usar.")
    elif os.path.exists('RGB_960m_256.onnx'):
        print("[OK] Modelo .onnx encontrado")
    else:
        print("[AVISO] Modelo não encontrado. Você precisará fornecer um modelo.")

    print("\n" + "="*60)
    print("Resumo")
    print("="*60)

    all_ok = all('OK' in v for v in results.values())

    if all_ok:
        print("✓ Todas as dependências estão instaladas!")
        print("\nPróximos passos:")
        print("1. Converta o modelo para .onnx (veja PRIMEIROS_PASSOS.md)")
        print("2. Execute: python main.py")
    else:
        print("✗ Alguns pacotes estão faltando.")
        print("\nInstale as dependências:")
        print("  pip install -r requirements.txt")

    print("="*60)

if __name__ == "__main__":
    test_imports()
