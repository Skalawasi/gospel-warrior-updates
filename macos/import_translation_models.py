#!/usr/bin/env python3
"""Bundle pinned OPUS-MT models for rate-limit-free, local study translation."""
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'gospel-warrior-study/assets/translation-models'
MODELS = {
    'fr': {'repository': 'michaelfeil/ct2fast-opus-mt-en-fr', 'revision': '55bcef18761227161433d86b81bbbcd9d813b429', 'files': ['model.bin', 'config.json', 'shared_vocabulary.txt', 'source.spm', 'target.spm', 'README.md']},
    'mg': {'repository': 'manancode/opus-mt-en-mg-ctranslate2-android', 'revision': '448c6832e8805f3afe6543f83eafb367f36a2a35', 'files': ['model.bin', 'config.json', 'shared_vocabulary.json', 'source.spm', 'target.spm', 'README.md']},
}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for language, model in MODELS.items():
        directory = OUTPUT / language
        directory.mkdir(exist_ok=True)
        files = {}
        for name in model['files']:
            url = f'https://huggingface.co/{model["repository"]}/resolve/{model["revision"]}/{name}'
            destination = directory / name
            if not destination.exists():
                print(f'Downloading {language}/{name}…', flush=True)
                response = requests.get(url, stream=True, timeout=180)
                response.raise_for_status()
                temporary = destination.with_suffix(destination.suffix + '.download')
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        stream.write(chunk)
                temporary.replace(destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            files[name] = {'sha256': digest, 'bytes': destination.stat().st_size, 'url': url}
        manifest[language] = {**model, 'files': files, 'baseModel': f'Helsinki-NLP/opus-mt-en-{language}', 'license': 'Apache-2.0'}
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Both local translation models are bundled.', flush=True)


if __name__ == '__main__':
    main()
