"""Offline OPUS-MT inference; no silent source-token or paragraph truncation."""
from __future__ import annotations

import importlib.util
import re
import threading
from pathlib import Path

MODELS = Path(__file__).resolve().parent / 'assets/translation-models'
_engines = {}
_engine_lock = threading.Lock()
PROVIDER = 'Local OPUS-MT (machine translation)'
_protected = re.compile(r'(https?://\S+|[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]+|[\U0001f000-\U0001ffff]+)')


def available(language):
    return language in ('fr', 'mg') and (MODELS / language / 'model.bin').is_file() and importlib.util.find_spec('ctranslate2') is not None and importlib.util.find_spec('sentencepiece') is not None


def engine(language):
    with _engine_lock:
        if language not in _engines:
            import ctranslate2
            import sentencepiece
            root = MODELS / language
            _engines[language] = (
                sentencepiece.SentencePieceProcessor(model_file=str(root / 'source.spm')),
                sentencepiece.SentencePieceProcessor(model_file=str(root / 'target.spm')),
                ctranslate2.Translator(str(root), device='cpu', compute_type='int8', intra_threads=2, inter_threads=1),
                threading.Lock(),
            )
        return _engines[language]


def token_groups(tokens, limit=240):
    """Partition every token, preferably at a word boundary."""
    start = 0
    while start < len(tokens):
        end = min(start + limit, len(tokens))
        if end < len(tokens):
            boundary = end
            while boundary > start + limit // 2 and not tokens[boundary].startswith('▁'):
                boundary -= 1
            if boundary > start + limit // 2:
                end = boundary
        yield tokens[start:end]
        start = end


def translate(text, language):
    src, dst, model, lock = engine(language)
    # Keep line/paragraph breaks, original Hebrew/Greek, emoji, and source URLs.
    parts = re.split(r'(\n+)', text)
    fragments, inputs = [], []
    for line in parts:
        if not line.strip() or '\n' in line:
            fragments.append(line)
            continue
        segments = _protected.split(line)
        for segment in segments:
            if not segment or _protected.fullmatch(segment) or not re.search(r'[A-Za-z]', segment):
                fragments.append(segment)
                continue
            prefix = re.match(r'^\s*', segment)[0]
            suffix = re.search(r'\s*$', segment)[0]
            source = segment.strip()
            if source.isupper() and len(source) > 25:
                source = source.capitalize()
            groups = list(token_groups(src.encode(source, out_type=str)))
            # Both bundled Marian configs require the caller to append EOS.
            # Missing it causes runaway repetition, even on a short sentence.
            first = len(inputs)
            inputs.extend(group + ['</s>'] for group in groups)
            fragments.append((prefix, suffix, first, len(groups)))
    with lock:
        results = model.translate_batch(inputs, max_batch_size=12, beam_size=2, max_input_length=0, max_decoding_length=768) if inputs else []
    output = []
    for fragment in fragments:
        if isinstance(fragment, str):
            output.append(fragment)
        else:
            prefix, suffix, first, count = fragment
            translated = []
            for result in results[first:first + count]:
                tokens = result.hypotheses[0]
                if not tokens or len(tokens) >= 768:
                    raise ValueError('Local translation did not finish; no partial study was saved.')
                value = dst.decode(tokens).strip()
                if not value:
                    raise ValueError('Local translation returned empty text.')
                translated.append(value)
            output.append(prefix + ' '.join(translated) + suffix)
    return ''.join(output)
