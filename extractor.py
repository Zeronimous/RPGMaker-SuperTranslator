import os
import json
import csv
import re

DATA_DIR = 'data/'
OUTPUT_CSV = 'traducciones.csv'
TEXT_KEYS = {'name', 'description', 'profile', 'displayName'}
EXCLUDED_FILES = {'Animations.json'}
EVENT_TEXT_CODES = {401, 405}
EVENT_CHOICE_CODE = 102

def is_skippable(value):
    return not value or not isinstance(value, str) or value.strip() == "" or value.startswith('◆')

def yield_text(base_id, text):
    """
    Ayudante para generar texto. Si el texto contiene saltos de línea (como '\\n'),
    lo divide y añade sufijos al ID.
    """
    if '\\n' in text:
        lines = text.split('\\n')
        for i, line in enumerate(lines):
            if line:
                yield {'id': f"{base_id}_{i+1}", 'text': line}
    else:
        yield {'id': base_id, 'text': text}

def find_translatable_text(data, path, filename):
    if isinstance(data, dict):
        is_map_event = 'pages' in data and 'name' in data and filename.startswith('Map')
        is_common_event = 'list' in data and 'name' in data and filename == 'CommonEvents.json'
        is_event_obj = is_map_event or is_common_event

        if 'code' in data and 'parameters' in data:
            code = data.get('code', 0)
            if code in EVENT_TEXT_CODES:
                text = data['parameters'][0]
                if not is_skippable(text):
                    yield from yield_text(f"{filename}:{path}:parameters[0]", text)
            elif code == EVENT_CHOICE_CODE:
                choices = data['parameters'][0]
                for i, choice in enumerate(choices):
                    if not is_skippable(choice):
                        yield from yield_text(f"{filename}:{path}:parameters[0][{i}]", choice)
            return

        for key, value in data.items():
            if is_event_obj and key == 'name':
                continue
            new_path = f"{path}:{key}" if path else key
            if key in TEXT_KEYS and not is_skippable(value):
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
    if 'terms' in data:
        terms = data['terms']
        for category in ['basic', 'commands', 'params']:
            if category in terms:
                for i, text in enumerate(terms[category]):
                    if not is_skippable(text):
                        yield from yield_text(f"{filename}:terms:{category}[{i}]", text)
        if 'messages' in terms:
            for key, text in terms['messages'].items():
                if not is_skippable(text):
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
