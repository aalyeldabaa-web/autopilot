#!/usr/bin/env python3
"""Deterministic first-pass task classifier, Arabic / English / mixed. Importable (classify()) or CLI.
Heuristics only; the model may override with a stated reason. Stores nothing.
Conservative by design: T (trivial) requires positive evidence (a trivial keyword, a short prompt, no heavier
signal). A prompt whose vocabulary the lists do not cover is never T, and its confidence is reported as low."""
import sys, json, re, pathlib, unicodedata

AR = r"[؀-ۿ]"

def normalize(text):
    t = unicodedata.normalize("NFKC", text)
    t = re.sub(r"[ً-ْـ]", "", t)          # diacritics and tatweel
    t = re.sub(r"[أإآٱ]", "ا", t); t = t.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    return t.lower()

PREFIX = r"(?:و|ف|ب|ك|ل|ال|وال|بال|فال|كال|لل|وب|ولل)?"
SUFFIX = r"(?:ات|ه|ين|ون|ي|ك|نا|هم|ها|كم)?"
def ar(*words):
    """Arabic keywords, normalized like the prompt, allowing attached prefixes (و ف ب ك ل ال) and suffixes,
    with lookarounds instead of \\b (unreliable around Arabic letters). A word may carry its own lookahead."""
    body = "|".join((normalize(w) if "(" in w else re.escape(normalize(w))) for w in words)
    return r"(?<![؀-ۿ])" + PREFIX + r"(?:" + body + r")" + SUFFIX + r"(?![؀-ۿ])"
def en(*words): return r"\b(?:" + "|".join(words) + r")\b"

KW = {
    "trivial": [en(r"typo", r"rename", r"comment", r"log line", r"version bump", r"whitespace", r"formatting", r"lint fix", r"small fix", r"one[- ]liner", r"tweak"),
                ar("خطا املائي", "تصحيح املائي", "اعاده تسميه", "تعليق", "سطر لوج", "تعديل بسيط", "تغيير بسيط", "تغيير صغير", "تعديل صغير", "حاجه صغيره", "حاجه بسيطه")],
    "explore": [en(r"where (?:is|are|does)", r"find (?:the|where|all)", r"which file", r"how does", r"what does", r"explain", r"trace", r"locate", r"look for", r"search for"),
                ar("فين", "اين", "وين", "ابحث", "دور علي", "دور على", "كيف يعمل", "ازاي بيشتغل", "اشرح", "تتبع", "حدد مكان", "في انهي ملف", "في اي ملف")],
    "security": [en(r"auth", r"login", r"password", r"token", r"secret", r"credential", r"payment", r"billing", r"crypto", r"encrypt", r"permission", r"acl", r"injection", r"xss", r"csrf", r"pii", r"gdpr", r"session cookie"),
                 ar("مصادقه", "تسجيل الدخول", "كلمه المرور", "كلمه السر", "باسورد", "توكن", "سر", "اسرار", "بيانات الاعتماد", "دفع", "مدفوعات", "فوتره", "تشفير", "صلاحيات", "حقن", "جلسه", "كوكيز", "بيانات شخصيه")],
    "architecture": [en(r"architect", r"redesign", r"migrate", r"migration", r"restructure", r"rewrite", r"design doc", r"schema change", r"cross[- ]cutting", r"refactor (?:the|whole|entire|all)"),
                     ar("معماري", "معماريه", "هيكله", "اعاده هيكله", "ترحيل", "اعاده تصميم", "اعاده كتابه", "تغيير المخطط", "مخطط قاعده البيانات", "سكيما", "ريفاكتور", "اعاده بناء")],
    "broad": [en(r"all files", r"across the (?:codebase|repo|project)", r"every (?:module|file|service|endpoint)", r"entire (?:codebase|repo|project)", r"whole (?:codebase|repo|project)"),
              ar("كل الملفات", "المشروع كله", "كل الموديولات", "كل الخدمات", "على مستوى المشروع", "علي مستوى المشروع", "النظام بالكامل", "الريبو كله", "الكود كله", "كل الكود", "بالكامل")],
    "debug": [en(r"bug", r"broken", r"fails?", r"failing", r"crash", r"error", r"exception", r"flaky", r"regression", r"doesn'?t work", r"not working", r"stack ?trace", r"[45]\d\d", r"expired", r"timeout", r"returns? (?:an? )?(?:error|null|nothing|wrong)"),
              ar("خطا(?! املايي)", "عطل", "مش شغال", "مش بيشتغل", "لا يعمل", "بيقع", "بتقع", "تقع", "يتعطل", "استثناء", "انهيار", "مشكله", "باج", "بج", "ايرور", "كراش", "بيرجع غلط", "غلط", "مش راضي", "ميرجعش")],
    "tests": [en(r"tests?", r"spec", r"coverage"), ar("اختبار", "اختبارات", "تغطيه", "تست", "تستات", "يونت تست")],
    "destructive": [en(r"delete", r"drop", r"wipe", r"force[- ]push", r"reset --hard", r"rm -rf", r"prod(?:uction)?"),
                    ar("احذف", "حذف", "امسح", "مسح", "انتاج", "برودكشن", "البرود", "فورس بوش")],
}
PATH_RX = r"[\w./\\-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|kt|rb|php|cs|c|cpp|h|md|json|ya?ml|toml|sql|html|css|vue|svelte)\b"

def language(text):
    arabic = len(re.findall(AR, text)); latin = len(re.findall(r"[A-Za-z]", text))
    if arabic and latin: return "mixed" if min(arabic, latin) / max(arabic, latin) > 0.15 else ("ar" if arabic > latin else "en")
    return "ar" if arabic else ("en" if latin else "unknown")

def classify(prompt, env=None, calib=None, cfg=None):
    env, calib, cfg = env or {}, calib or {}, cfg or {}
    thr = cfg.get("direct_file_threshold", 3); min_n = cfg.get("estimate_min_samples", 5)
    lang = language(prompt); p = normalize(prompt); words = len(p.split())
    paths = len(set(re.findall(PATH_RX, prompt)))
    f = {k: any(re.search(rx, p) for rx in rxs) for k, rxs in KW.items()}
    signals = sum(f.values()) + (1 if paths else 0)
    score = 0
    score += 0 if words < 25 else 1 if words < 80 else 2 if words < 200 else 3
    score += 0 if paths < 2 else 1 if paths < 5 else 2
    score += 2 if f["architecture"] else 0
    score += 2 if f["broad"] else 0
    score += 1 if f["debug"] else 0
    score += 1 if f["security"] else 0
    if env.get("repo_files", 0) > 2000 and (f["explore"] or f["broad"] or f["debug"]): score += 1
    trivial_ok = f["trivial"] and words < 40 and not (f["architecture"] or f["broad"] or f["security"] or f["debug"])
    if trivial_ok: score -= 2
    if signals == 0 and words >= 8: score = max(score, 1)                                 # unknown vocabulary: at least S
    if lang in ("ar", "mixed") and not f["trivial"] and words >= 12: score = max(score, 1)   # non-English without trivial evidence: at least S
    cls = "T" if score <= 0 else "S" if score <= 2 else "M" if score <= 4 else "L"
    if cls == "T" and not trivial_ok: cls = "S"
    confidence = "high" if signals >= 3 or (trivial_ok and signals >= 1) else "medium" if signals >= 1 else "low"
    if confidence == "low" and cls == "T": cls = "S"
    needs_explore = f["explore"] or f["broad"] or (paths == 0 and cls in ("M", "L"))
    route = {"T": "direct", "S": "direct" if (paths <= thr and not f["broad"]) else "builder",
             "M": "plan>builder>reviewer", "L": "architect>builders(worktree)>reviewer-deep"}[cls]
    if f["security"] and cls != "T" and "reviewer-deep" not in route: route += "+reviewer-deep"
    if needs_explore and cls != "T": route = "scout>" + route
    gates = {"T": "deterministic checks", "S": "tests+lint", "M": "tests+lint+review", "L": "tests+lint+deep review"}[cls]
    c = calib.get(cls) or {}
    if c.get("n", 0) >= min_n:
        est = f"{c['p25']//1000}k-{c['p75']//1000}k tokens, ~{c['median_duration_s']/60:.0f} min (calibrated, n={c['n']})"
    else:
        est = "low confidence: no calibrated history for this class yet"
    return {"class": cls, "score": score, "confidence": confidence, "language": lang, "flags": [k for k, v in f.items() if v],
            "paths": paths, "words": words, "needs_exploration": needs_explore, "route": route, "gates": gates, "estimate": est}

if __name__ == "__main__":
    here = pathlib.Path(__file__).resolve().parent.parent
    def load(n):
        try: return json.loads((here / n).read_text(encoding="utf-8"))
        except Exception: return {}
    text = " ".join(sys.argv[1:]) or sys.stdin.read()
    print(json.dumps(classify(text, load("env.json"), load("calibration.json"), load("config.json")), indent=1, ensure_ascii=False))
