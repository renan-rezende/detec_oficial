# ✅ CSV Separado Por Câmera

## Mudança Implementada

Agora **cada câmera tem seu próprio arquivo CSV** usando o nome da câmera.

---

## Antes ❌

**Problema**: Todas as câmeras salvavam no mesmo CSV (`data/detections.csv`)

```
data/
└── detections.csv  ← Todas as câmeras aqui
```

**CSV unificado**:
```csv
Data,camera_name,total_pellets,media,...
2026-03-05 10:00:00,Camera_01,150,10.5,...
2026-03-05 10:00:01,Camera_02,120,9.8,...
2026-03-05 10:00:02,Camera_01,148,10.4,...
```

---

## Agora ✅

**Solução**: Cada câmera tem seu CSV individual

```
data/
├── Camera_01.csv  ← Dados da Camera_01
├── Camera_02.csv  ← Dados da Camera_02
└── Linha_A.csv    ← Dados da Linha_A
```

**CSVs separados**:

**data/Camera_01.csv**:
```csv
Data,camera_name,total_pellets,media,...
2026-03-05 10:00:00,Camera_01,150,10.5,...
2026-03-05 10:00:02,Camera_01,148,10.4,...
2026-03-05 10:00:04,Camera_01,152,10.6,...
```

**data/Camera_02.csv**:
```csv
Data,camera_name,total_pellets,media,...
2026-03-05 10:00:01,Camera_02,120,9.8,...
2026-03-05 10:00:03,Camera_02,118,9.7,...
```

---

## Vantagens

### 1. **Organização**
- Fácil identificar dados de cada câmera
- Arquivos separados = mais limpo

### 2. **Performance**
- Arquivos menores = leitura mais rápida
- Menos conflitos de escrita

### 3. **Análise Individual**
- Abrir CSV específico no Excel
- Analisar apenas uma câmera

### 4. **Backup Seletivo**
- Fazer backup de câmeras específicas
- Deletar histórico de uma câmera sem afetar outras

### 5. **Escalabilidade**
- 10 câmeras = 10 arquivos pequenos
- Melhor que 1 arquivo gigante

---

## Como Funciona

### 1. **Ao Adicionar Câmera**

```python
# camera_manager.py (linha ~78)

# Nome do arquivo baseado no nome da câmera
csv_filename = f"{config.name.replace(' ', '_')}.csv"
csv_path = os.path.join('data', csv_filename)

# Criar CSVLogger específico
self.csv_loggers[camera_id] = CSVLogger(csv_path)
```

**Exemplo**:
- Câmera: `"Linha 1"` → CSV: `data/Linha_1.csv`
- Câmera: `"Camera_02"` → CSV: `data/Camera_02.csv`

### 2. **Ao Processar Frame**

```python
# camera_manager.py (linha ~196)

# Usar CSVLogger específico desta câmera
csv_logger = self.csv_loggers[camera_id]
csv_logger.log(config.name, analysis)
```

Cada thread de câmera grava **apenas no seu CSV**.

### 3. **Visualização de Histórico**

```python
# history_view.py (linha ~90)

# Ler TODOS os CSVs da pasta data/
csv_files = glob.glob(os.path.join('data', '*.csv'))

# Combinar todos em um único DataFrame
dfs = []
for csv_file in csv_files:
    df_temp = pd.read_csv(csv_file)
    dfs.append(df_temp)

df = pd.concat(dfs, ignore_index=True)
```

A tela de histórico **combina automaticamente** todos os CSVs.

---

## Estrutura de Dados

### CSVLogger por Câmera

```python
# camera_manager.py

self.csv_loggers = {
    'camera_id_001': CSVLogger('data/Camera_01.csv'),
    'camera_id_002': CSVLogger('data/Camera_02.csv'),
    'camera_id_003': CSVLogger('data/Linha_A.csv'),
}
```

### Mapeamento

| Camera ID | Nome Câmera | Arquivo CSV |
|-----------|-------------|-------------|
| `b81fb1f5` | Camera_01 | `data/Camera_01.csv` |
| `a92de3c7` | Linha A | `data/Linha_A.csv` |
| `c73af4b2` | Esteira 2 | `data/Esteira_2.csv` |

---

## Fluxo Completo

```
┌─────────────────────────────────────────────────┐
│ 1. Adicionar Câmera "Camera_01"                │
├─────────────────────────────────────────────────┤
│ CameraManager.add_camera()                      │
│   → Criar CSVLogger('data/Camera_01.csv')       │
│   → Salvar em self.csv_loggers[camera_id]      │
└─────────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────┐
│ 2. Thread processa frames                      │
├─────────────────────────────────────────────────┤
│ Detectar pelotas → Analisar                     │
│   → Pegar CSVLogger da câmera                   │
│   → csv_logger.log(analysis)                    │
│   → Grava em data/Camera_01.csv                │
└─────────────────────────────────────────────────┘
               ↓
┌─────────────────────────────────────────────────┐
│ 3. Visualizar Histórico                         │
├─────────────────────────────────────────────────┤
│ HistoryViewWindow                                │
│   → glob.glob('data/*.csv')                     │
│   → Ler todos CSVs                              │
│   → pd.concat() → DataFrame unificado           │
│   → Plotar gráfico com filtro por câmera       │
└─────────────────────────────────────────────────┘
```

---

## Arquivos Modificados

### 1. **core/camera_manager.py**

**Mudanças**:
- Linha 37-48: Remover parâmetro `csv_logger` do construtor
- Linha 48: Adicionar `self.csv_loggers = {}` (dict de CSVLoggers)
- Linha 78-82: Criar CSVLogger específico ao adicionar câmera
- Linha 196-197: Usar CSVLogger específico da câmera
- Linha 271: Limpar `csv_loggers` ao parar câmera

### 2. **ui/app.py**

**Mudanças**:
- Linha 6: Remover `from core.csv_logger import CSVLogger`
- Linha 27-28: Remover criação de CSVLogger global
- Linha 28: `CameraManager()` sem parâmetro
- Linha 82: Passar `camera_manager` para HistoryViewWindow

### 3. **ui/history_view.py**

**Mudanças**:
- Linha 8: Adicionar `import glob, os`
- Linha 21: Receber `camera_manager` em vez de `csv_logger`
- Linha 24: Armazenar `self.camera_manager`
- Linha 90-118: Ler TODOS os CSVs com `glob` e combinar com `pd.concat()`

---

## Testes Recomendados

### 1. **Adicionar Múltiplas Câmeras**
```
1. Adicionar "Camera_01"
   → Verificar: data/Camera_01.csv existe
2. Adicionar "Linha A"
   → Verificar: data/Linha_A.csv existe
3. Processar frames
   → Verificar: cada CSV tem dados da câmera correta
```

### 2. **Verificar CSVs Separados**
```
1. Abrir data/Camera_01.csv no Excel
   → Deve ter APENAS dados de Camera_01
2. Abrir data/Linha_A.csv
   → Deve ter APENAS dados de Linha A
```

### 3. **Visualizar Histórico**
```
1. Clicar em "Histórico"
   → Deve mostrar TODAS as câmeras no gráfico
2. Selecionar "Camera_01" no filtro
   → Deve mostrar apenas linha de Camera_01
3. Selecionar "Todas"
   → Deve mostrar todas as câmeras
```

---

## Exemplo Prático

### Cenário: 3 Câmeras em Operação

**Câmeras**:
1. Camera_01 (Linha de produção 1)
2. Camera_02 (Linha de produção 2)
3. Esteira_Principal (Esteira principal)

**Estrutura de arquivos**:
```
data/
├── Camera_01.csv           (50 MB)
├── Camera_02.csv           (48 MB)
└── Esteira_Principal.csv   (62 MB)
```

**Antes** (CSV único): `detections.csv` (160 MB) - lento, difícil de gerenciar

**Agora** (CSVs separados): 3 arquivos menores - rápido, organizado

---

## Limpeza de Dados

### Deletar histórico de UMA câmera:
```bash
del data\Camera_01.csv
```
Outras câmeras **não são afetadas**.

### Deletar TUDO:
```bash
del data\*.csv
```

---

## Compatibilidade

✅ **Retrocompatível**: Se você já tinha `data/detections.csv`, ele **NÃO será usado** mais.

⚠️ **Nova câmera = novo CSV**: Ao adicionar câmera, cria CSV automaticamente.

✅ **Histórico unificado**: A tela de histórico combina TODOS os CSVs automaticamente.

---

## Resumo

| Aspecto | Antes | Agora |
|---------|-------|-------|
| **Arquivos CSV** | 1 único arquivo | 1 por câmera |
| **Nome do arquivo** | `detections.csv` | `<nome_camera>.csv` |
| **Organização** | Ruim (tudo misturado) | Excelente (separado) |
| **Performance** | Lenta (arquivo grande) | Rápida (arquivos pequenos) |
| **Análise individual** | Difícil (filtrar manual) | Fácil (abrir CSV específico) |
| **Backup** | Tudo ou nada | Seletivo por câmera |
| **Histórico UI** | Ler 1 arquivo | Ler e combinar N arquivos |

**Status**: ✅ **Sistema agora cria CSV separado por câmera automaticamente!**
