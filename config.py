"""
Configurações globais do sistema de detecção de pelotas
"""
import os

# Caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'RGB_960m_256.engine')
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
CSV_PATH = os.path.join(DATA_DIR, 'detections.csv')
LOG_PATH = os.path.join(LOGS_DIR, 'app.log')

# Faixas granulométricas (em mm)
GRANULOMETRIC_RANGES = {
    'range_below_6': (0, 6.3),
    'range_6_8': (6.3, 8.0),
    'range_8_9': (8.0, 9.0),
    'range_9_12': (9.0, 12.0),
    'range_12_16': (12.0, 16.0),
    'range_16_19': (16.0, 19.0),
    'range_above_19': (19.0, float('inf'))
}

# Ordem das faixas para exibição
RANGE_ORDER = [
    'range_below_6',
    'range_6_8',
    'range_8_9',
    'range_9_12',
    'range_12_16',
    'range_16_19',
    'range_above_19'
]

# Labels das faixas para exibição
RANGE_LABELS = {
    'range_below_6': '< 6.3 mm',
    'range_6_8': '6.3-8 mm',
    'range_8_9': '8-9 mm',
    'range_9_12': '9-12 mm',
    'range_12_16': '12-16 mm',
    'range_16_19': '16-19 mm',
    'range_above_19': '> 19 mm'
}

# Colunas do CSV
CSV_COLUMNS = [
    'Data',
    'camera_name',
    'total_pellets',
    'media',
    'range_below_6',
    'range_6_8',
    'range_8_9',
    'range_9_12',
    'range_12_16',
    'range_16_19',
    'range_above_19'
]

# Configurações padrão do detector
DEFAULT_CONFIDENCE = 0.5
DEFAULT_DETECTION_RATE = 5  # Inferências por segundo (1-10)
DEFAULT_SCALE_MM_PIXEL = 0.1  # mm/pixel
DEFAULT_MODEL_INPUT_SIZE = (960, 960)

# Configurações de UI
UI_UPDATE_INTERVAL = 30  # ms
HISTORY_UPDATE_INTERVAL = 5000  # ms (5 segundos)

# Configurações de threading
MAX_QUEUE_SIZE = 10
