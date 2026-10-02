"""Which language a reply is in, and which voice says it.

Every engine keeps one voice per language (`voices.<engine>.<en|pt>` in the
config); `lang auto` picks the slot per reply. With `random` on, each reply
draws from the engine's whole catalog for that language instead.
"""
import random
import re
import shutil
import subprocess

LANGS = ("en", "pt")

GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

CATALOG = {
    # Gemini voices are multilingual: the same list serves both languages.
    "gemini": {"en": GEMINI_VOICES, "pt": GEMINI_VOICES},
    "sano": {"en": ["heart", "hfc", "amy", "kristin"], "pt": ["pt-cadu"]},
    "kokoro": {
        "en": ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam",
               "am_michael", "am_fenrir", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"],
        "pt": ["pf_dora", "pm_alex", "pm_santa"],
    },
    # say is filled in from `say -v ?`, which knows what this Mac has installed.
}

DEFAULT_VOICES = {
    "gemini": {"en": "Kore", "pt": "Kore"},
    "sano": {"en": "heart", "pt": "pt-cadu"},
    "kokoro": {"en": "af_heart", "pt": "pf_dora"},
    "say": {"en": "Samantha", "pt": "Luciana"},
}

# Words that carry every sentence and exist in only one of the two languages.
# Anything that is also an English word ("as", "no", "do", "um") stays out:
# one of those tipped "committed as d57f2bd" into Portuguese.
PT_WORDS = frozenset(
    "o e quer pronto feito certo beleza que não é de da dos das uma para com os "
    "você está isso isto mas se na nos nas por pra também já ainda quando como "
    "sim foi são vai tem ele ela eu ao aos à mais muito seu sua esse essa este "
    "esta então agora qual quais quem onde porque devo posso podemos prefere "
    "precisa precisamos usar fazer deve deveria".split())
EN_WORDS = frozenset(
    "done okay sure yes the is and to of a you it that this for with are not be "
    "on in can but i was will have has what if does an at by from or so all just "
    "now then there here which would should could your my we they both also "
    "fixed added".split())
assert not PT_WORDS & EN_WORDS
PT_MARKS_RE = re.compile(r"[ãõçáéíóúâêôà]", re.I)
WORD_RE = re.compile(r"[^\W\d_]+", re.U)


def detect(text):
    """'pt', 'en', or None when the text gives no signal ("Done.", "Pronto.").

    Counting function words is enough to tell these two apart, costs
    microseconds, and English code terms inside a Portuguese reply don't tip
    it: the sentence's own glue words outnumber them.
    """
    words = WORD_RE.findall(text.lower())
    pt = sum(w in PT_WORDS for w in words) + 2 * len(PT_MARKS_RE.findall(text))
    en = sum(w in EN_WORDS for w in words)
    if pt == en:
        return None
    return "pt" if pt > en else "en"


def lang_for(text, cfg, previous=None):
    """The language to speak text in. A reply with no signal of its own keeps
    the language of the one before it -- the conversation hasn't switched."""
    fixed = cfg.get("lang", "auto")
    if fixed in LANGS:
        return fixed
    return detect(text) or (previous if previous in LANGS else "en")


def _say_catalog():
    if not shutil.which("say"):
        return {"en": [], "pt": []}
    try:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return {"en": [], "pt": []}
    found = {"en": [], "pt": []}
    for line in out.splitlines():
        m = re.match(r"^(.+?)\s+([a-z]{2})_[A-Z]{2}\s", line)
        if m and m.group(2) in found:
            found[m.group(2)].append(m.group(1).strip())
    return found


def catalog(engine, lang):
    if engine == "say":
        return _say_catalog()[lang]
    return CATALOG.get(engine, {}).get(lang, [])


def configured(cfg, engine, lang):
    return (cfg.get("voices", {}).get(engine, {}).get(lang)
            or DEFAULT_VOICES[engine][lang])


def pick(cfg, engine, lang):
    """The voice for this reply: the configured one, or a random draw."""
    if cfg.get("random"):
        options = catalog(engine, lang)
        if options:
            return random.choice(options)
    return configured(cfg, engine, lang)


def lang_of_voice(engine, name):
    """Which slot a voice name belongs in, or None if it isn't recognised."""
    for lang in LANGS:
        if name in catalog(engine, lang):
            return lang
    if engine == "kokoro" and len(name) > 2 and name[1] in "fm" and name[2] == "_":
        return "pt" if name[0] == "p" else "en"
    if engine == "sano" and name.startswith("pt-"):
        return "pt"
    return None
