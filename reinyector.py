import os
import json
import csv
import re
from collections import defaultdict

# Directorio donde se encuentran los archivos de datos de RPG Maker MZ
DATA_DIR = 'data/'
# Archivo CSV de entrada con las traducciones
INPUT_CSV = 'traducciones.csv'

def set_value_by_path(data, path, value):
    """
    Navega por una estructura de datos (diccionarios/listas) usando un path y establece un valor.
    El path es una cadena como 'events[1]:pages[0]:list[1]:parameters[0]'.
    """
    keys = re.split(r'[:\[\]]+', path)
    keys = [k for k in keys if k]  # Eliminar cadenas vacías

    current_element = data
    for i, key in enumerate(keys[:-1]):
        if key.isdigit():
            idx = int(key)
            if isinstance(current_element, list) and idx < len(current_element):
                current_element = current_element[idx]
            else:
                # El path no es válido en la estructura actual
                raise KeyError(f"Índice fuera de rango: {key} en el path {path}")
        else:
            if isinstance(current_element, dict) and key in current_element:
                current_element = current_element[key]
            else:
                # El path no es válido
                raise KeyError(f"Clave no encontrada: {key} en el path {path}")

    final_key = keys[-1]
    if final_key.isdigit():
        idx = int(final_key)
        if isinstance(current_element, list) and idx < len(current_element):
            current_element[idx] = value
        else:
            raise KeyError(f"Índice final fuera de rango: {final_key} en el path {path}")
    else:
        if isinstance(current_element, dict):
            current_element[final_key] = value
        else:
            raise KeyError(f"El elemento final no es un diccionario para la clave: {final_key} en el path {path}")


def main():
    """Función principal del script."""
    if not os.path.exists(INPUT_CSV):
        print(f"Error: El archivo de traducciones '{INPUT_CSV}' no fue encontrado.")
        return

    # Agrupar traducciones por archivo para procesar un archivo a la vez
    translations_by_file = defaultdict(list)
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'id' in row and 'text' in row and row['id'] and row['text'] is not None:
                    try:
                        filename, path = row['id'].split(':', 1)
                        translations_by_file[filename].append({'path': path, 'text': row['text']})
                    except ValueError:
                        print(f"  Advertencia: Fila mal formada en CSV, saltando: {row}")

    except FileNotFoundError:
        print(f"Error: No se pudo encontrar el archivo {INPUT_CSV}")
        return
    except Exception as e:
        print(f"Error leyendo el archivo CSV: {e}")
        return

    print("Iniciando reinyección de textos...")

    for filename, translations in translations_by_file.items():
        filepath = os.path.join(DATA_DIR, filename)

        if not os.path.exists(filepath):
            print(f"  Advertencia: No se encontró el archivo de datos {filepath}, saltando...")
            continue

        print(f"Procesando: {filename} ({len(translations)} entradas)")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for t in translations:
                try:
                    set_value_by_path(data, t['path'], t['text'])
                except (KeyError, IndexError) as e:
                    print(f"  Error al procesar la ID '{t['path']}' en {filename}: {e}. Saltando esta entrada.")

            # Escribir el archivo JSON modificado
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except json.JSONDecodeError:
            print(f"  Error: No se pudo decodificar JSON en {filename}.")
        except Exception as e:
            print(f"  Error inesperado procesando {filename}: {e}")

    print("\nReinyección completada.")

if __name__ == '__main__':
    main()
