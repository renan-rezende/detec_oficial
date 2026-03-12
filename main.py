"""
Ponto de entrada do aplicativo Pellet Detector
Sistema de detecção e medição de pelotas de minério
"""
import sys
import os

# Adicionar diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Desabilitar chamadas de rede do ultralytics ANTES de qualquer import
# Obrigatório para ambientes sem internet (servidores industriais)
os.environ['YOLO_OFFLINE'] = '1'
os.environ['ULTRALYTICS_OFFLINE'] = '1'

# Configurar logging
from utils.logger import setup_logger
logger = setup_logger('PelletDetector')

def main():
    """Função principal"""
    try:
        logger.info("="*60)
        logger.info("Iniciando Pellet Detector")
        logger.info("="*60)

        # Importar e executar app
        from ui.app import run_app
        run_app()

    except KeyboardInterrupt:
        logger.info("Aplicação interrompida pelo usuário")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
