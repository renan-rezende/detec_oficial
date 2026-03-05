"""
Script para gerar executável com PyInstaller
"""
import PyInstaller.__main__
import os
import sys

def build():
    """Gera executável"""

    # Caminho do projeto
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, 'RGB_960m_256.engine')

    # Verificar se modelo existe
    if not os.path.exists(model_path):
        print(f"AVISO: Modelo não encontrado em {model_path}")
        print("O executável será criado mas você precisará fornecer o modelo separadamente")

    # Argumentos do PyInstaller
    args = [
        'main.py',
        '--name=PelletDetector',
        '--onefile',
        '--windowed',
        '--noconfirm',

        # Adicionar modelo (se existir)
        f'--add-data={model_path};.' if os.path.exists(model_path) else None,

        # Adicionar temas do CustomTkinter
        '--collect-all=customtkinter',

        # Hidden imports
        '--hidden-import=PIL',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=cv2',
        '--hidden-import=numpy',
        '--hidden-import=pandas',
        '--hidden-import=matplotlib',
        '--hidden-import=onnxruntime',

        # Excluir pacotes desnecessários (reduzir tamanho)
        '--exclude-module=pytest',
        '--exclude-module=IPython',
        '--exclude-module=notebook',

        # Console para debug (remover --windowed se quiser ver console)
        # '--console',
    ]

    # Filtrar None
    args = [arg for arg in args if arg is not None]

    print("="*60)
    print("Gerando executável com PyInstaller")
    print("="*60)
    print(f"Diretório: {base_dir}")
    print(f"Modelo: {'Incluído' if os.path.exists(model_path) else 'NÃO incluído'}")
    print("="*60)

    # Executar PyInstaller
    PyInstaller.__main__.run(args)

    print("\n" + "="*60)
    print("Build concluído!")
    print("="*60)
    print(f"Executável: {os.path.join(base_dir, 'dist', 'PelletDetector.exe')}")
    print("="*60)

    # Instruções
    print("\nPróximos passos:")
    print("1. O executável está em: dist/PelletDetector.exe")
    print("2. Se o modelo não foi incluído, copie RGB_960m_256.engine para o mesmo diretório do .exe")
    print("3. Teste o executável em uma máquina sem Python instalado")
    print("4. Se houver erros, execute novamente sem --windowed para ver mensagens de erro")

if __name__ == "__main__":
    build()
