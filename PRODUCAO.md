# 🏭 Guia de Deploy em Produção — Pellet Detector

Guia completo para colocar o sistema em funcionamento em servidor industrial **sem acesso à internet**.

---

## ⚠️ Premissas Importantes

1. **O arquivo `.engine` não é portável entre máquinas.**
   Deve ser gerado diretamente no servidor de produção a partir do `.pt`.

2. **O executável é uma pasta (`--onedir`), não um arquivo único.**
   Copie a pasta `dist/PelletDetector/` inteira — nunca apenas o `.exe`.

3. **As pastas `data/` e `logs/` são criadas ao lado do `.exe` automaticamente.**
   Não dentro de `%TEMP%` nem dentro da pasta do Python.

---

## 📋 Requisitos do Servidor de Produção

| Componente | Requisito |
|------------|-----------|
| **OS** | Windows 10/11 ou Windows Server 2019/2022 |
| **GPU** | NVIDIA com suporte CUDA (Turing/Ampere recomendado) |
| **Driver NVIDIA** | Versão 520+ (para CUDA 11.8+) |
| **CUDA Toolkit** | 11.8 ou 12.x (mesma versão do ambiente de build) |
| **TensorRT** | 8.x ou 10.x (compatível com driver instalado) |
| **RAM** | 8 GB mínimo, 16 GB recomendado |
| **Disco** | 10 GB livres (para executável + CSVs históricos) |
| **Rede** | Não necessária em operação (offline total) |

---

## 🚀 Processo Completo de Deploy

### Etapa 1 — Preparar na máquina de desenvolvimento

```bash
# No ambiente de desenvolvimento, gerar o executável
python build_executable.py
```

Resultado: pasta `dist/PelletDetector/`

### Etapa 2 — Transferir para o servidor

Copie para o servidor (via pendrive, rede local, etc.):
- A pasta completa `dist/PelletDetector/`
- O arquivo `RGB_960m_256.pt` (modelo PyTorch — para gerar o engine)
- O script `conv.py` (para compilar o engine no servidor)

**Estrutura no servidor:**
```
C:\PelletDetector\          ← pasta do executável
├── PelletDetector.exe
├── ... (DLLs e dependências)
│
C:\PelletDetector_setup\    ← pasta temporária de setup
├── RGB_960m_256.pt
└── conv.py
```

### Etapa 3 — Instalar dependências no servidor

Instalar (apenas uma vez):

1. **Driver NVIDIA** — versão compatível com a GPU do servidor
2. **CUDA Toolkit** — mesma versão usada no build
3. **TensorRT** — via `pip install tensorrt` ou pacote NVIDIA
4. **Python 3.10+** — apenas para rodar `conv.py`
5. **Ultralytics** — `pip install ultralytics` (apenas para `conv.py`)

> Todos esses instaladores devem ser baixados na máquina de desenvolvimento
> e levados ao servidor via mídia física (pendrive/HD externo).

### Etapa 4 — Compilar o modelo TensorRT no servidor

```bash
# Na pasta onde está conv.py e RGB_960m_256.pt
python conv.py
```

Isso gera `RGB_960m_256.engine` **otimizado para a GPU do servidor**.

### Etapa 5 — Mover o engine para a pasta do executável

```
C:\PelletDetector\RGB_960m_256.engine   ← copiar aqui
```

### Etapa 6 — Primeira execução e validação

```bash
# Executar diretamente (modo console para ver erros)
C:\PelletDetector\PelletDetector.exe
```

Verificar:
- [ ] A interface abre normalmente
- [ ] A pasta `C:\PelletDetector\data\` é criada
- [ ] A pasta `C:\PelletDetector\logs\` é criada
- [ ] O log `logs\app.log` é criado e tem conteúdo
- [ ] Ao adicionar câmera, o modelo carrega sem erro

---

## 🔄 Rotina de Operação

### Iniciar o sistema
Duplo clique em `PelletDetector.exe` ou criar atalho na área de trabalho.

### Monitorar logs
```
C:\PelletDetector\logs\app.log        ← log atual
C:\PelletDetector\logs\app.log.1      ← backup anterior
...
C:\PelletDetector\logs\app.log.5      ← backup mais antigo
```
Rotação automática: máx 5 MB por arquivo, 5 backups mantidos.

### Dados gerados
```
C:\PelletDetector\data\Camera_01.csv
C:\PelletDetector\data\Linha_A.csv
...
```
Um CSV por câmera, crescimento contínuo. **Configure backup periódico.**

### Backup recomendado
```batch
REM Executar via Task Scheduler diariamente
xcopy /Y /I "C:\PelletDetector\data\*.csv" "\\servidor_backup\pellet\data\"
xcopy /Y /I "C:\PelletDetector\logs\*.log" "\\servidor_backup\pellet\logs\"
```

---

## 🔧 Comportamento em Caso de Falha

### Câmera perde conexão (RTSP/IP)
O sistema **tenta reconectar automaticamente** a cada 5 segundos.
Não é necessária intervenção manual para reconexões de rede.

### Câmera aparece como "Parado" na lista
A thread da câmera encerrou por erro fatal (ex.: modelo corrompido).
1. Verifique `logs\app.log` para identificar o erro
2. Clique em "Parar" para limpar o estado
3. Clique em "+ Adicionar Câmera" para reiniciar

### Aplicativo fecha inesperadamente
- Verifique `logs\app.log` — erros críticos são registrados antes do fechamento
- Verifique se há memória/VRAM suficiente disponível

---

## 📁 Estrutura Final no Servidor

```
C:\PelletDetector\
├── PelletDetector.exe           ← executável principal
├── RGB_960m_256.engine          ← modelo compilado para ESTA GPU
├── ... (DLLs CUDA, ultralytics, etc.)
│
├── data\                        ← criado automaticamente
│   ├── Camera_01.csv
│   └── Linha_A.csv
│
└── logs\                        ← criado automaticamente
    ├── app.log
    ├── app.log.1
    └── ...
```

---

## ❗ Avisos de Segurança

- **Não conecte o servidor à internet** durante operação (configuração isolada)
- **Não atualize drivers NVIDIA** sem recompilar o `.engine` com `conv.py`
- **Não mova a pasta** `PelletDetector\` após configurar — os CSVs históricos ficam dentro dela
- **Faça backup dos CSVs regularmente** — são o único registro histórico das medições

---

**Versão do documento**: 2.0
**Atualizado**: Março 2026
**Status**: ✅ Validado para deploy offline
