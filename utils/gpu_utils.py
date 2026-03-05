"""
Utilitários para detecção e gerenciamento de GPUs NVIDIA
"""
import subprocess
import logging


logger = logging.getLogger('PelletDetector.gpu_utils')


def list_nvidia_gpus():
    """
    Lista GPUs NVIDIA disponíveis no sistema

    Returns:
        list: Lista de dicionários com informações das GPUs
              [{'id': 0, 'name': 'NVIDIA GeForce RTX 3060', 'memory': '12288 MiB'}, ...]
              Retorna lista vazia se nenhuma GPU encontrada
    """
    gpus = []

    try:
        # Tentar usando nvidia-smi
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 3:
                        gpus.append({
                            'id': int(parts[0].strip()),
                            'name': parts[1].strip(),
                            'memory': f"{parts[2].strip()} MB"
                        })

            logger.info(f"Encontradas {len(gpus)} GPU(s) NVIDIA")
            return gpus

    except FileNotFoundError:
        logger.warning("nvidia-smi não encontrado. Drivers NVIDIA não instalados?")
    except subprocess.TimeoutExpired:
        logger.error("Timeout ao executar nvidia-smi")
    except Exception as e:
        logger.error(f"Erro ao listar GPUs: {e}")

    # Fallback: tentar detectar via ONNX Runtime
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            gpus.append({
                'id': 0,
                'name': 'GPU NVIDIA (detectada via ONNX Runtime)',
                'memory': 'N/A'
            })
            logger.info("GPU NVIDIA detectada via ONNX Runtime")
    except ImportError:
        logger.debug("ONNX Runtime não disponível para detecção de GPU")
    except Exception as e:
        logger.debug(f"Erro ao detectar GPU via ONNX Runtime: {e}")

    return gpus


def get_gpu_options():
    """
    Retorna lista de opções de GPU para UI

    Returns:
        list: Lista de strings no formato "GPU 0: Name" ou ["CPU"] se nenhuma GPU
    """
    gpus = list_nvidia_gpus()

    if not gpus:
        return ["CPU"]

    options = [f"GPU {gpu['id']}: {gpu['name']}" for gpu in gpus]
    options.append("CPU")

    return options


def parse_device_option(option_str):
    """
    Converte opção de UI para formato de device

    Args:
        option_str: String como "GPU 0: NVIDIA GeForce RTX 3060" ou "CPU"

    Returns:
        str: "cuda:0", "cuda:1", ou "cpu"
    """
    if option_str.startswith("GPU"):
        try:
            gpu_id = int(option_str.split(":")[0].replace("GPU", "").strip())
            return f"cuda:{gpu_id}"
        except:
            return "cpu"
    return "cpu"


if __name__ == "__main__":
    # Teste
    print("GPUs disponíveis:")
    gpus = list_nvidia_gpus()
    if gpus:
        for gpu in gpus:
            print(f"  GPU {gpu['id']}: {gpu['name']} ({gpu['memory']})")
    else:
        print("  Nenhuma GPU encontrada")

    print("\nOpções para UI:")
    for opt in get_gpu_options():
        device = parse_device_option(opt)
        print(f"  {opt} -> {device}")
