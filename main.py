"""
Ponto de entrada do aplicativo Pellet Detector
Sistema de deteccao e medicao de pelotas de minerio
"""
import sys
import os
import logging
import multiprocessing as mp

# Adicionar diretorio do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Desabilitar chamadas de rede do ultralytics ANTES de qualquer import
# Obrigatorio para ambientes sem internet (servidores industriais)
os.environ['YOLO_OFFLINE'] = '1'
os.environ['ULTRALYTICS_OFFLINE'] = '1'

# Nivel de log: DEBUG ativado por --debug ou pela variavel de ambiente PELLET_DEBUG=1
_debug_mode = '--debug' in sys.argv or os.environ.get('PELLET_DEBUG', '0') == '1'
_log_level = logging.DEBUG if _debug_mode else logging.INFO

# Configurar logging
from utils.logger import setup_logger
logger = setup_logger('PelletDetector', level=_log_level)

def main():
    """Funcao principal"""
    try:
        logger.info("="*60)
        logger.info("Iniciando Pellet Detector")
        if _debug_mode:
            logger.info("MODO DEBUG ATIVADO — logs de desempenho detalhados habilitados")
        logger.info("="*60)

        # Importar e executar app
        from ui.app import run_app
        run_app()

    except KeyboardInterrupt:
        logger.info("Aplicacao interrompida pelo usuario")
        sys.exit(0)

    except Exception as e:
        logger.critical(f"Erro fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Necessario para multiprocessing no Windows (metodo spawn)
    mp.freeze_support()
    main()
