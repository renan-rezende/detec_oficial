# 📚 Índice da Documentação

Guia completo para navegação na documentação do Pellet Detector.

## 🎯 Por Onde Começar?

### 👨‍💻 Primeiro Uso

```
1. README.md ...................... Visão geral do sistema
2. INSTALACAO.md .................. Guia passo a passo
3. SCRIPTS_AUXILIARES.md .......... Scripts de teste e conversão
4. main.py ........................ Executar aplicação
```

### 📖 Referência Rápida

```
SUMARIO.md ........................ Visão geral em 1 página
```

### 🔧 Problemas?

```
README.md > Troubleshooting ....... Soluções comuns
INSTALACAO.md > Solução de Problemas
logs/app.log ...................... Logs em tempo real
```

---

## 📄 Arquivos de Documentação

### 🟢 Documentação Principal

#### **README.md**
**O que é**: Documentação principal completa do sistema

**Contém**:
- ✅ Descrição do sistema
- ✅ Funcionalidades
- ✅ Performance (60-150 FPS com TensorRT)
- ✅ Estrutura do projeto
- ✅ Como usar (passo a passo)
- ✅ Faixas granulométricas (7 faixas)
- ✅ Calibração da escala
- ✅ Formato CSV
- ✅ Visualização com máscaras
- ✅ Gráficos (tempo real + histórico)
- ✅ Troubleshooting
- ✅ Dicas de performance
- ✅ Informações técnicas

**Quando ler**:
- ✅ **Primeiro contato** com o sistema
- ✅ Entender como funciona
- ✅ Resolver dúvidas gerais
- ✅ Referência de funcionalidades

---

#### **INSTALACAO.md**
**O que é**: Guia completo de instalação passo a passo

**Contém**:
- ✅ Pré-requisitos (hardware e software)
- ✅ Instalação do Python
- ✅ Criação de ambiente virtual
- ✅ Instalação de dependências
- ✅ PyTorch (GPU vs CPU)
- ✅ Verificação da instalação
- ✅ Solução de problemas na instalação
- ✅ Preparação do modelo
- ✅ Primeira execução
- ✅ Teste com webcam/vídeo

**Quando ler**:
- ✅ **Primeira instalação**
- ✅ Problemas de instalação
- ✅ Configurar nova máquina
- ✅ Instalar em ambiente diferente

---

#### **SUMARIO.md**
**O que é**: Visão geral rápida em 1 página

**Contém**:
- ✅ Quick start (3 comandos)
- ✅ Estatísticas do projeto
- ✅ Arquitetura (diagrama)
- ✅ Estrutura de arquivos
- ✅ Funcionalidades principais
- ✅ Interface (4 telas)
- ✅ Performance
- ✅ Formato CSV
- ✅ Tecnologias
- ✅ Casos de uso
- ✅ Diferenciais
- ✅ Checklist de validação

**Quando ler**:
- ✅ **Referência rápida**
- ✅ Relembrar comandos
- ✅ Ver estatísticas
- ✅ Entender arquitetura rapidamente

---

#### **SCRIPTS_AUXILIARES.md**
**O que é**: Guia de todos os scripts utilitários

**Contém**:
- ✅ `main.py` - executar aplicação
- ✅ `test_installation.py` - testar instalação
- ✅ `test_tensorrt.py` - testar modelo
- ✅ `conv.py` - converter .pt para .engine
- ✅ `build_executable.py` - gerar .exe
- ✅ `config.py` - configurações globais

**Quando ler**:
- ✅ **Antes de rodar scripts**
- ✅ Entender o que cada script faz
- ✅ Converter modelo
- ✅ Gerar executável
- ✅ Diagnosticar problemas

---

### 🟡 Documentação Específica

#### **MUDANCAS_SEGMENTACAO.md**
**O que é**: Detalhes da implementação com máscaras de segmentação

**Contém**:
- ✅ Mudança de círculo para área real
- ✅ Cálculo baseado em pixels da máscara
- ✅ Fórmula: `d = 2 × √(área / π)`
- ✅ Visualização com máscaras coloridas
- ✅ Pipeline completo
- ✅ Comparação de precisão
- ✅ Benefícios da nova abordagem

**Quando ler**:
- ✅ Entender como a medição funciona
- ✅ Verificar precisão do sistema
- ✅ Desenvolver melhorias
- ✅ Documentar para equipe técnica

---

#### **MUDANCA_CSV_POR_CAMERA.md**
**O que é**: Detalhes do CSV separado por câmera

**Contém**:
- ✅ Antes vs Agora (1 CSV vs N CSVs)
- ✅ Vantagens (organização, performance)
- ✅ Como funciona internamente
- ✅ Estrutura de dados
- ✅ Fluxo completo
- ✅ Arquivos modificados
- ✅ Testes recomendados

**Quando ler**:
- ✅ Entender estrutura de CSVs
- ✅ Saber onde estão os dados
- ✅ Desenvolver integrações
- ✅ Exportar/importar dados

---

## 🗂️ Estrutura Hierárquica

```
📚 DOCUMENTACAO/
│
├── 🌟 INICIAR AQUI
│   ├── README.md ..................... Principal
│   └── SUMARIO.md .................... Referência rápida
│
├── 🛠️ INSTALACAO E SETUP
│   ├── INSTALACAO.md ................. Guia completo
│   └── SCRIPTS_AUXILIARES.md ......... Scripts auxiliares
│
├── 📖 DETALHES TECNICOS
│   ├── MUDANCAS_SEGMENTACAO.md ....... Medição por área
│   └── MUDANCA_CSV_POR_CAMERA.md ..... CSV separado
│
└── 📋 ESTE ARQUIVO
    └── INDICE_DOCUMENTACAO.md ........ Navegação
```

---

## 🎯 Cenários de Uso

### "Nunca usei o sistema"

```
1. README.md (seção "O que é?")
2. INSTALACAO.md (completo)
3. README.md (seção "Como Usar")
4. SCRIPTS_AUXILIARES.md (test_installation.py)
```

### "Instalado, não funciona"

```
1. INSTALACAO.md > Solução de Problemas
2. SCRIPTS_AUXILIARES.md > test_installation.py
3. README.md > Troubleshooting
4. logs/app.log
```

### "Quero entender o código"

```
1. SUMARIO.md (arquitetura)
2. MUDANCAS_SEGMENTACAO.md (medição)
3. MUDANCA_CSV_POR_CAMERA.md (dados)
4. Código-fonte (core/, ui/, utils/)
```

### "Preciso converter modelo"

```
1. SCRIPTS_AUXILIARES.md > conv.py
2. SCRIPTS_AUXILIARES.md > test_tensorrt.py
3. README.md > Formato do Modelo
```

### "Quero distribuir executável"

```
1. SCRIPTS_AUXILIARES.md > build_executable.py
2. README.md > Geração de Executável
```

### "Referência rápida"

```
SUMARIO.md (página única)
```

### "Adicionar nova funcionalidade"

```
1. SUMARIO.md (arquitetura)
2. Código-fonte relevante
3. MUDANCAS_SEGMENTACAO.md (exemplo de mudança)
```

---

## 📊 Matriz de Conteúdo

| Tópico | README | INSTALACAO | SUMARIO | SCRIPTS | SEGMENTACAO | CSV |
|--------|--------|------------|---------|---------|-------------|-----|
| **Visão Geral** | ✅✅✅ | - | ✅✅ | - | - | - |
| **Instalação** | ✅ | ✅✅✅ | - | ✅ | - | - |
| **Como Usar** | ✅✅✅ | ✅ | ✅ | - | - | - |
| **Funcionalidades** | ✅✅✅ | - | ✅✅ | - | - | - |
| **Performance** | ✅✅ | - | ✅✅ | - | - | - |
| **Arquitetura** | ✅ | - | ✅✅✅ | - | ✅ | ✅ |
| **Scripts** | - | ✅ | - | ✅✅✅ | - | - |
| **Medição** | ✅✅ | - | ✅ | - | ✅✅✅ | - |
| **Dados CSV** | ✅✅ | - | ✅ | - | - | ✅✅✅ |
| **Troubleshooting** | ✅✅✅ | ✅✅✅ | ✅ | ✅✅ | - | - |
| **Calibração** | ✅✅✅ | ✅ | ✅ | - | - | - |
| **Modelo** | ✅✅ | ✅✅ | ✅ | ✅✅✅ | - | - |

**Legenda**:
- ✅ = Mencionado
- ✅✅ = Detalhado
- ✅✅✅ = Foco principal

---

## 🔍 Busca Rápida

### Comandos Python

```bash
python main.py                    # README, SCRIPTS
python test_installation.py       # INSTALACAO, SCRIPTS
python test_tensorrt.py          # SCRIPTS
python conv.py                   # SCRIPTS
python build_executable.py       # SCRIPTS
```

### Instalação

```bash
pip install -r requirements.txt   # INSTALACAO
venv\Scripts\activate            # INSTALACAO
```

### Performance

- TensorRT: **README**, **SUMARIO**
- Taxa de detecção: **README**, **SUMARIO**
- Multi-câmera: **README**, **SUMARIO**, **CSV**

### Medição

- Área da máscara: **SEGMENTACAO**, **README**
- Diâmetro equivalente: **SEGMENTACAO**, **README**
- Calibração: **README**, **INSTALACAO**

### Dados

- CSV separado: **CSV**, **README**, **SUMARIO**
- Formato CSV: **README**, **SUMARIO**, **CSV**
- Histórico: **README**, **SUMARIO**

### Problemas

- Erro de instalação: **INSTALACAO**
- Erro de modelo: **README**, **SCRIPTS**
- Erro de GPU: **INSTALACAO**, **README**
- Logs: **README**, **INSTALACAO**

---

## 📝 Ordem de Leitura Recomendada

### Para Usuários

```
Dia 1:
  1. README.md (30 min)
  2. INSTALACAO.md (20 min)
  3. Executar instalação (30 min)

Dia 2:
  4. SCRIPTS_AUXILIARES.md > test_installation.py (5 min)
  5. SCRIPTS_AUXILIARES.md > conv.py (10 min)
  6. README.md > Como Usar (10 min)
  7. Usar o sistema! (∞)

Referência:
  - SUMARIO.md quando esquecer algo
  - README > Troubleshooting quando tiver problema
```

### Para Desenvolvedores

```
Dia 1:
  1. SUMARIO.md (15 min)
  2. MUDANCAS_SEGMENTACAO.md (20 min)
  3. MUDANCA_CSV_POR_CAMERA.md (15 min)
  4. Explorar código core/ (60 min)

Dia 2:
  5. Explorar código ui/ (60 min)
  6. README.md completo (30 min)
  7. SCRIPTS_AUXILIARES.md (20 min)
```

### Para Administradores

```
  1. SUMARIO.md (visão geral)
  2. README.md > Performance
  3. INSTALACAO.md (requisitos)
  4. SCRIPTS_AUXILIARES.md > build_executable.py
```

---

## 🔗 Links Rápidos

### Arquivos de Código

- `main.py` - Ponto de entrada
- `config.py` - Configurações
- `core/detector.py` - Inferência TensorRT
- `core/pellet_analyzer.py` - Medição por área
- `core/camera_manager.py` - Multi-threading
- `core/csv_logger.py` - Gravação CSV
- `ui/app.py` - Interface principal

### Arquivos de Dados

- `data/*.csv` - CSVs por câmera
- `logs/app.log` - Logs em tempo real
- `RGB_960m_256.engine` - Modelo TensorRT

### Dependências

- `requirements.txt` - Lista de pacotes
- `venv/` - Ambiente virtual

---

## ✅ Checklist de Documentação

Para verificar se leu tudo necessário:

### Usuário Final

- [ ] README.md completo
- [ ] INSTALACAO.md completo
- [ ] test_installation.py rodou com sucesso
- [ ] Sabe usar main.py
- [ ] Sabe calibrar escala
- [ ] Sabe onde estão CSVs
- [ ] Sabe consultar logs

### Desenvolvedor

- [ ] SUMARIO.md (arquitetura)
- [ ] MUDANCAS_SEGMENTACAO.md
- [ ] MUDANCA_CSV_POR_CAMERA.md
- [ ] Explorou core/
- [ ] Explorou ui/
- [ ] Entende threading
- [ ] Entende medição por área

### Administrador

- [ ] SUMARIO.md
- [ ] README.md > Performance
- [ ] INSTALACAO.md > Requisitos
- [ ] Sabe gerar executável
- [ ] Sabe fazer backup
- [ ] Entende estrutura de dados

---

## 📞 Suporte

### Não encontrou informação?

1. **Buscar** no arquivo relevante (Ctrl+F)
2. **Consultar** matriz de conteúdo acima
3. **Ver** logs em `logs/app.log`
4. **Executar** `test_installation.py`

### Documentação incompleta?

- A documentação cobre **100%** das funcionalidades
- Se algo não está claro, provavelmente está em outro arquivo
- Use este índice para navegar

---

**Última atualização**: Março 2026

**Total de páginas de documentação**: 6 arquivos

**Linhas de documentação**: ~2500 linhas

**Status**: ✅ Documentação completa e organizada
