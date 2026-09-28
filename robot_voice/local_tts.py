"""Local engines, run inside the Python that has them installed.

  python -m robot_voice.local_tts <engine> <voice> <out.wav> [length_scale] < text

The core stays stdlib-only and never imports sanotts, kokoro or numpy itself:
it runs this module with `engine.local_python()`, a separate environment
holding the heavy packages, so the hook's own python3 needs none of them.
"""
import os
import sys
import urllib.request
import warnings
import wave

# sano voices the pip package doesn't know yet, fetched from Hugging Face.
SANO_HF_VOICES = {"pt-cadu": "pt-cadu-1p57m"}
SANO_HF_URL = "https://huggingface.co/ampixa/sanoTTS/resolve/main/%s/%s"
SANO_HF_FILES = ("manifest.json", "piper-phoneme-config.json", "weights.fp16.bin")
SANO_CACHE = os.path.expanduser("~/.cache/sanotts")


def _sano_voice_dir(package):
    path = os.path.join(SANO_CACHE, package)
    for name in SANO_HF_FILES:
        target = os.path.join(path, name)
        if not os.path.exists(target):
            os.makedirs(path, exist_ok=True)
            urllib.request.urlretrieve(SANO_HF_URL % (package, name), target + ".part")
            os.replace(target + ".part", target)
    return path


def sano(text, voice, scale):
    import sanotts
    if voice in SANO_HF_VOICES:
        # No built-in text frontend for these languages yet: espeak-ng does it.
        synth = sanotts.Synthesizer(voice_dir=_sano_voice_dir(SANO_HF_VOICES[voice]),
                                    piperlite_g2p="espeak")
    else:
        synth = sanotts.Synthesizer(voice)
    res = synth.synthesize(text, duration_length_scale=scale)
    return res.audio, res.sample_rate


def kokoro(text, voice, scale):
    import numpy as np
    from kokoro import KPipeline
    # A voice's first letter is its language: a(merican), b(ritish), p(ortuguese)...
    pipe = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")
    chunks = [a for _, _, a in pipe(text, voice=voice, speed=1.0 / (scale or 1.0))]
    if not chunks:
        raise RuntimeError("kokoro produced no audio")
    return np.concatenate(chunks), 24000


ENGINES = {"sano": sano, "kokoro": kokoro}


def write_wav(path, audio, rate):
    import numpy as np
    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm.tobytes())


def main(argv):
    engine, voice, out = argv[0], argv[1], argv[2]
    scale = float(argv[3]) if len(argv) > 3 and argv[3] else None
    text = sys.stdin.read().strip()
    if not text:
        return 0
    warnings.filterwarnings("ignore")
    audio, rate = ENGINES[engine](text, voice, scale)
    write_wav(out, audio, rate)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ImportError as e:
        print("not installed: %s" % e, file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print("%s: %s" % (type(e).__name__, e), file=sys.stderr)
        sys.exit(1)
