import os
import json
import csv
import re

DATA_DIR = 'data/'
OUTPUT_CSV = 'traducciones.csv'

# Claves que son siempre nombres de archivo y deben ser ignoradas
FILENAME_KEYS = {'battleback1Name', 'battleback2Name', 'parallaxName', 'characterName', 'faceName'}
# Claves "padre" que indican que una clave "name" hija es un nombre de archivo de audio
AUDIO_PARENT_KEYS = {'bgm', 'bgs', 'me', 'se'}
# Claves que generalmente contienen texto seguro para traducir
SAFE_TEXT_KEYS = {'name', 'description', 'displayName', 'profile', 'message1', 'message2', 'message3', 'message4'}

EXCLUDED_FILES = {'Animations.json', 'MapInfos.json', 'Tilesets.json'}
EVENT_TEXT_CODES = {401, 405}
EVENT_CHOICE_CODE = 102

def is_skippable(value):
    if not value or not isinstance(value, str):
        return True

    stripped_value = value.strip()
    return not stripped_value or stripped_value.startswith('◆') or stripped_value.startswith('--')

def yield_text(base_id, text):
    """
    Ayudante para generar texto. Normaliza los saltos de línea y, si el texto
    es multilínea, lo divide y añade sufijos al ID. Filtra líneas no deseadas.
    """
    normalized_text = text.replace('\\n', '\n')
    if '\n' in normalized_text:
        lines = normalized_text.split('\n')
        for i, line in enumerate(lines):
            if not is_skippable(line):
                yield {'id': f"{base_id}_{i+1}", 'text': line}
    else:
        if not is_skippable(normalized_text):
            yield {'id': base_id, 'text': normalized_text}

def find_translatable_text(data, path, filename):
    if isinstance(data, dict):
        # Rama 1: Manejar comandos de evento
        if 'code' in data and 'parameters' in data:
            code = data.get('code', 0)
            if code in EVENT_TEXT_CODES:
                text = data['parameters'][0]
                yield from yield_text(f"{filename}:{path}:parameters[0]", text)
            elif code == EVENT_CHOICE_CODE:
                choices = data['parameters'][0]
                for i, choice in enumerate(choices):
                    yield from yield_text(f"{filename}:{path}:parameters[0][{i}]", choice)
            elif code == 122:
                # Manejo especial para Control de Variables -> Script
                # Parámetro 3 es el tipo de operando, 4 es 'Script'
                if len(data['parameters']) > 4 and data['parameters'][3] == 4:
                    text = data['parameters'][4]
                    # Extraer solo si parece una cadena de texto entrecomillada
                    if isinstance(text, str) and text.startswith('"') and text.endswith('"'):
                         yield {'id': f"{filename}:{path}:parameters[4]", 'text': text}

        # Rama 2: Manejar todos los demás objetos (no son comandos de evento)
        else:
            parent_key = path.split(':')[-1] if path else ''

            for key, value in data.items():
                # Regla 1: Ignorar claves que son nombres de archivo
                if key in FILENAME_KEYS:
                    continue
                # Regla 2: Ignorar 'name' si el padre es un objeto de audio
                if key == 'name' and parent_key in AUDIO_PARENT_KEYS:
                    continue

                # Regla 3: Ignorar 'name' de un objeto de evento
                is_map_event = 'pages' in data and 'name' in data and filename.startswith('Map')
                is_common_event = 'list' in data and 'name' in data and filename == 'CommonEvents.json'
                if (is_map_event or is_common_event) and key == 'name':
                    continue

                new_path = f"{path}:{key}" if path else key
                if key in SAFE_TEXT_KEYS and value:
                    yield from yield_text(f"{filename}:{new_path}", value)
                else:
                    yield from find_translatable_text(value, new_path, filename)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            if item is None:
                continue
            new_path = f"{path}[{i}]"
            yield from find_translatable_text(item, new_path, filename)

def extract_text_from_system(data, path, filename):
    # Procesar los arrays de "tipos"
    type_arrays = ['armorTypes', 'elements', 'equipTypes', 'skillTypes', 'weaponTypes']
    for array_name in type_arrays:
        if array_name in data and isinstance(data[array_name], list):
            for i, text in enumerate(data[array_name]):
                # El primer elemento a menudo es nulo o vacío
                if i == 0 and not text:
                    continue
                if text:
                    yield from yield_text(f"{filename}:{array_name}[{i}]", text)

    # Procesar el objeto "terms"
    if 'terms' in data:
        terms = data['terms']
        for category in ['basic', 'commands', 'params']:
            if category in terms:
                for i, text in enumerate(terms[category]):
                    if text: # Añadida comprobación para evitar valores nulos
                        yield from yield_text(f"{filename}:terms:{category}[{i}]", text)
        if 'messages' in terms:
            for key, text in terms['messages'].items():
                if text: # Añadida comprobación para evitar valores nulos
                    yield from yield_text(f"{filename}:terms:messages:{key}", text)

def main():
    all_texts = []
    processed_ids = set()

    if not os.path.exists(DATA_DIR):
        print(f"Error: El directorio '{DATA_DIR}' no fue encontrado.")
        return

    print("Iniciando extracción de texto...")

    for filename in sorted(os.listdir(DATA_DIR)):
        if not filename.endswith('.json') or filename in EXCLUDED_FILES:
            continue

        filepath = os.path.join(DATA_DIR, filename)
        print(f"Procesando: {filename}")
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if not data:
                    continue

                results = []
                if filename == 'System.json':
                    results = list(extract_text_from_system(data, '', filename))
                else:
                    results = list(find_translatable_text(data, '', filename))

                for item in results:
                    if item['id'] not in processed_ids:
                        all_texts.append(item)
                        processed_ids.add(item['id'])

            except json.JSONDecodeError:
                print(f"  Advertencia: No se pudo decodificar JSON en {filename}.")
            except Exception as e:
                print(f"  Error inesperado procesando {filename}: {e}")

    all_texts.sort(key=lambda x: x['id'])

    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=['id', 'text'])
            writer.writeheader()
            writer.writerows(all_texts)
        print(f"\nExtracción completada. Se encontraron {len(all_texts)} líneas de texto.")
        print(f"Archivo de salida: {OUTPUT_CSV}")
    except IOError:
        print(f"Error: No se pudo escribir en el archivo {OUTPUT_CSV}.")

if __name__ == '__main__':
    main()
