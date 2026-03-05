"""
Sistema de logging configurado para o aplicativo
"""
import logging
import os
from config import LOG_PATH, LOGS_DIR


def setup_logger(name='PelletDetector', level=logging.INFO):
    """
    Configura e retorna um logger

    Args:
        name: Nome do logger
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configurado
    """
    # Criar diretório de logs se não existir
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

    # Criar logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar duplicação de handlers
    if logger.handlers:
        return logger

    # Formato das mensagens
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Handler para arquivo
    file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


# Logger global do aplicativo
app_logger = setup_logger()
