"""
Script para gerar executável com PyInstaller
Uso: python build_executable.py

IMPORTANTE:
- Use --onedir (pasta) em vez de --onefile para aplicações com CUDA/TensorRT
- --onefile extrai tudo em temp a cada execução (lento e problemático com GPU)
- O diretório dist/PelletDetector/ deve ser copiado inteiro para o servidor
"""
import PyInstaller.__main__
import os
import sys


def build():
    """Gera executável no formato --onedir (recomendado para CUDA/TensorRT)"""

    base_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("Gerando executável com PyInstaller (--onedir)")
    print("=" * 60)
    print(f"Diretório base: {base_dir}")
    print()

    # Verificar modelos disponíveis
    model_engine = os.path.join(base_dir, 'RGB_960m_256.engine')
    model_pt = os.path.join(base_dir, 'RGB_960m_256.pt')
    model_onnx = os.path.join(base_dir, 'RGB_960m_256.onnx')

    print("Modelos encontrados:")
    print(f"  .engine : {'SIM' if os.path.exists(model_engine) else 'NAO'} — {model_engine}")
    print(f"  .pt     : {'SIM' if os.path.exists(model_pt) else 'NAO'}")
    print(f"  .onnx   : {'SIM' if os.path.exists(model_onnx) else 'NAO'}")
    print()
    print("AVISO: O arquivo .engine NAO e portavel entre maquinas.")
    print("       O .engine deve ser gerado no proprio servidor de producao.")
    print("       Use conv.py no servidor para gerar o .engine a partir do .pt")
    print()

    # Argumentos do PyInstaller
    args = [
        'main.py',
        '--name=PelletDetector',
        '--onedir',          # PASTA, não arquivo único — obrigatório para CUDA
        '--noconfirm',
        '--clean',

        # Temas do CustomTkinter (necessário para UI funcionar)
        '--collect-all=customtkinter',

        # Ultralytics e dependências (modelos YOLO, configs, etc.)
        '--collect-all=ultralytics',

        # TensorRT — inclui as DLLs nativas (sem isso: "DLL load failed while importing tensorrt")
        # Nomes dos módulos Python (não dos pacotes pip)
        '--collect-all=tensorrt',
        '--collect-all=tensorrt_libs',    # tensorrt-cu13-libs
        '--collect-all=tensorrt_bindings', # tensorrt-cu13-bindings

        # Coletar dados do torch (necessário para TensorRT via Ultralytics)
        '--collect-data=torch',

        # Hidden imports essenciais
        '--hidden-import=PIL',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        '--hidden-import=cv2',
        '--hidden-import=numpy',
        '--hidden-import=pandas',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.backends.backend_tkagg',
        '--hidden-import=onnxruntime',
        '--hidden-import=torch',
        '--hidden-import=torch.jit',
        '--hidden-import=torchvision',

        # Excluir pacotes desnecessários (reduzir tamanho)
        '--exclude-module=pytest',
        '--exclude-module=IPython',
        '--exclude-module=notebook',
        '--exclude-module=jupyterlab',
        '--exclude-module=scipy',
        '--exclude-module=sklearn',

        # Manter console visível para ver erros em produção
        # Remova --console e use --windowed somente após validar funcionamento
        '--console',
    ]

    print("Executando PyInstaller...")
    print("(Isso pode demorar 5-15 minutos na primeira vez)")
    print()

    PyInstaller.__main__.run(args)

    dist_dir = os.path.join(base_dir, 'dist', 'PelletDetector')
    print()
    print("=" * 60)
    print("Build concluido!")
    print("=" * 60)
    print(f"Executavel gerado em: {dist_dir}")
    print()
    print("PROXIMOS PASSOS PARA PRODUCAO:")
    print()
    print("1. Copie a PASTA dist/PelletDetector/ para o servidor")
    print("   (nao apenas o .exe, toda a pasta)")
    print()
    print("2. No servidor de producao, gere o .engine:")
    print("   a. Copie RGB_960m_256.pt para a pasta do executavel")
    print("   b. Execute: python conv.py")
    print("   c. O .engine sera gerado automaticamente")
    print()
    print("3. Coloque o .engine gerado na pasta do executavel")
    print()
    print("4. Execute PelletDetector.exe para testar")
    print()
    print("5. Verifique que as pastas data/ e logs/ sao criadas")
    print("   ao lado do PelletDetector.exe (nao dentro de %TEMP%)")
    print()
    print("ATENCAO: Instale os drivers NVIDIA e CUDA no servidor")
    print("         antes de executar o programa!")
    print("=" * 60)


if __name__ == "__main__":
    build()
