import os
import json
import csv
import re
from collections import defaultdict

DATA_DIR = 'data/'
INPUT_CSV = 'traducciones.csv'

# Expresiones regulares para la reinyección en los campos 'note'
# La clave debe coincidir con la usada en el extractor
NOTETAG_REGEXES = {
    'breakMsg': re.compile(r'(<breakMsg:)(.*?)(>)', re.IGNORECASE)
}

def set_value_by_path(data, path, value):
    keys = re.split(r'[:\[\]]+', path)
    keys = [k for k in keys if k]
    current_element = data
    for i, key in enumerate(keys[:-1]):
        if key.isdigit():
            current_element = current_element[int(key)]
        else:
            current_element = current_element[key]
    final_key = keys[-1]
    if final_key.isdigit():
        current_element[int(final_key)] = value
    else:
        current_element[final_key] = value

def get_value_by_path(data, path):
    keys = re.split(r'[:\[\]]+', path)
    keys = [k for k in keys if k]
    current_element = data
    for key in keys:
        if key.isdigit():
            current_element = current_element[int(key)]
        else:
            current_element = current_element[key]
    return current_element

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: El archivo de traducciones '{INPUT_CSV}' no fue encontrado.")
        return

    translations_by_file = defaultdict(list)
    try:
        with open(INPUT_CSV, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if 'id' in row and 'text' in row and row['id'] and row['text'] is not None:
                    translations_by_file[row['id'].split(':')[0]].append(row)
    except Exception as e:
        print(f"Error leyendo el archivo CSV: {e}")
        return

    print("Iniciando reinyección de textos...")

    for filename, rows in translations_by_file.items():
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  Advertencia: No se encontró el archivo de datos {filepath}, saltando...")
            continue

        print(f"Procesando: {filename}...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Separar traducciones normales, multilínea y de notetags
            grouped_multiline = defaultdict(dict)
            single_line = []
            notetags = []

            for row in rows:
                full_path = row['id'].split(':', 1)[1]

                # Intentar clasificar como notetag primero
                match_notetag = re.match(r'(.+):(\w+)$', full_path)
                if match_notetag:
                    path, tag_name = match_notetag.groups()
                    if tag_name in NOTETAG_REGEXES:
                        notetags.append({'path': path, 'tag': tag_name, 'text': row['text']})
                        continue

                # Si no es notetag, comprobar si es multilínea
                match_multiline = re.match(r'(.+)_(\d+)$', full_path)
                if match_multiline:
                    base_path, index = match_multiline.groups()
                    grouped_multiline[base_path][int(index)] = row['text']
                else:
                    # Si no, es una línea única
                    single_line.append({'path': full_path, 'text': row['text']})

            # 1. Inyectar textos de una sola línea
            for t in single_line:
                set_value_by_path(data, t['path'], t['text'])

            # 2. Inyectar textos multilínea reconstruidos
            for base_path, parts in grouped_multiline.items():
                final_text = "\n".join(parts[k] for k in sorted(parts.keys()))
                set_value_by_path(data, base_path, final_text)

            # 3. Inyectar textos de notetags con regex
            for tag_info in notetags:
                path = tag_info['path']
                tag_name = tag_info['tag']
                regex = NOTETAG_REGEXES[tag_name]

                original_string = get_value_by_path(data, path)
                # Construir el reemplazo: grupo1 + nuevo texto + grupo3
                new_string = regex.sub(r'\g<1>' + tag_info['text'] + r'\g<3>', original_string)
                set_value_by_path(data, path, new_string)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"  Error inesperado procesando {filename}: {e}")

    print("\nReinyección completada.")

if __name__ == '__main__':
    main()
