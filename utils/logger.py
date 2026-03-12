"""
Sistema de logging configurado para o aplicativo
"""
import logging
import logging.handlers
import os
from config import LOG_PATH, LOGS_DIR


def setup_logger(name='PelletDetector', level=logging.INFO):
    """
    Configura e retorna um logger com rotação de arquivo.

    Args:
        name: Nome do logger
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logger configurado
    """
    # Criar diretório de logs se não existir
    os.makedirs(LOGS_DIR, exist_ok=True)

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

    def _add(handler):
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # Handler para arquivo com rotação: máx 5 MB, mantém 5 backups
    _add(logging.handlers.RotatingFileHandler(
        LOG_PATH,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    ))

    # Handler para console
    _add(logging.StreamHandler())

    return logger
