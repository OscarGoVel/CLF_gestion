"""
Ejecuta este script en la misma carpeta que main.py.
Guardara cualquier error en 'ERROR_LOG.txt' y tambien
lo mostrara en pantalla sin cerrar la ventana.
"""
import sys
import traceback
import os

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ERROR_LOG.txt")
main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

try:
    with open(main_path, encoding="utf-8") as f:
        code = f.read()
    exec(code)

except Exception as e:
    error_msg = traceback.format_exc()

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== ERROR AL ABRIR main.py ===\n\n")
        f.write(error_msg)

    print("=" * 60)
    print("ERROR ENCONTRADO:")
    print("=" * 60)
    print(error_msg)
    print("=" * 60)
    print(f"\nEl error tambien fue guardado en:\n{log_path}")
    print("\nPresiona ENTER para cerrar...")
    input()
