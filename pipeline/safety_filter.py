import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .config import GENERATOR_CONFIG_PATH


@dataclass
class SafetyResult:
    ok: bool
    reasons: List[str]
    severity: str  # low|medium|high
    method: str  # heuristic|ollama
    category: str  # ok|sexual|minors|self_harm|hate|graphic_violence|doxxing|illegal|unknown

    def to_json(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": self.reasons,
            "severity": self.severity,
            "method": self.method,
            "category": self.category,
        }


def _load_generator_safety_config(path: str = GENERATOR_CONFIG_PATH) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        safety = cfg.get("safety") if isinstance(cfg, dict) else None
        return safety if isinstance(safety, dict) else {}
    except Exception:
        return {}


def _normalize(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _contains_any(text: str, patterns: List[str]) -> bool:
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True
    return False


def evaluate_safety(
    *,
    trend_data: Dict[str, Any],
    script: str,
    metadata: Dict[str, Any],
    safety_config: Optional[Dict[str, Any]] = None,
) -> SafetyResult:
    """
    Strict-ish safety filter for fully automated posting.
    Blocks content likely to violate platform policies or be inappropriate.
    """
    cfg = safety_config or _load_generator_safety_config()
    mode = (cfg.get("mode") or "strict").strip().lower()
    use_ollama = bool(cfg.get("use_ollama_if_available", True))

    title = _normalize(str(metadata.get("title") or trend_data.get("title") or ""))
    desc = _normalize(str(trend_data.get("description") or trend_data.get("text") or ""))
    script_n = _normalize(script or "")
    blob = " \n".join([title, desc[:2000], script_n[:3000]])

    reasons: List[str] = []

    # Hard blocks (high severity)
    sexual_explicit = [
        r"\brape\b", r"\bmolest", r"\bincest\b", r"\bchild porn",
        r"\bblowjob\b", r"\bhandjob\b", r"\banal sex\b", r"\bporn\b", r"\bonlyfans\b",
    ]
    minors = [r"\bunderage\b", r"\bminor\b", r"\bchild\b", r"\bteen\b", r"\b15\b|\b16\b|\b14\b|\b13\b"]
    self_harm = [r"\bsuicide\b", r"\bkill myself\b", r"\bself[- ]harm\b", r"\bcut myself\b", r"\boverdose\b"]
    # Actual identifiers, not the words: "kept my old phone number" is a normal story detail.
    doxxing = [
        r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b",
        r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b",
        r"\bsocial security\b", r"\bdoxx",
    ]
    graphic = [r"\bbeheaded\b", r"\bdismember", r"\bgore\b", r"\bguts\b", r"\bcorpse\b", r"\bgraphic\b"]
    hate = [
        r"\bnazi\b", r"\bkkk\b",
        # Slur detection is intentionally minimal here (avoid false positives); expand carefully if needed.
    ]
    illegal = [r"\bhow to\b.*\b(make|build)\b.*\b(bomb|pipe bomb)\b", r"\bsteal\b.*\bcredit card\b"]

    # Sexual content involving minors is the strictest.
    if _contains_any(blob, sexual_explicit) and _contains_any(blob, minors):
        reasons.append("sexual_content_involving_minors")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="minors")

    if _contains_any(blob, self_harm):
        reasons.append("self_harm")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="self_harm")

    if _contains_any(blob, doxxing):
        reasons.append("doxxing_or_personal_info")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="doxxing")

    if _contains_any(blob, illegal):
        reasons.append("illegal_instructions")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="illegal")

    if _contains_any(blob, sexual_explicit):
        reasons.append("explicit_sexual_content")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="sexual")

    if _contains_any(blob, graphic):
        reasons.append("graphic_violence_or_gore")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="graphic_violence")

    if _contains_any(blob, hate):
        reasons.append("hate_extremism")
        return SafetyResult(ok=False, reasons=reasons, severity="high", method="heuristic", category="hate")

    # Medium severity flags (allowed by default; Ollama can optionally veto).
    medium_flags = [
        (r"\bdrug(s)?\b|\bcocaine\b|\bheroin\b|\bmeth\b", "drug_content"),
        (r"\bdomestic violence\b|\babuse\b", "abuse_content"),
        (r"\bmurder(ed)?\b|\bstab(bed)?\b|\bshoot(ing|er|s)?\b|\bgun\b|\bknife\b|\bblood\b", "violence_keywords"),
    ]
    medium_hits = [name for pat, name in medium_flags if re.search(pat, blob, flags=re.IGNORECASE)]
    if medium_hits and use_ollama and mode == "strict":
        # If available, ask Ollama to decide; otherwise we allow (flagged).
        try:
            from .trend_analyzer import ollama_available, ollama_pick_model, ollama_chat

            if ollama_available():
                model = ollama_pick_model(None)
                if model:
                    prompt = (
                        "Classify if this Reddit-story YouTube Shorts script is safe to auto-upload.\n"
                        "Return JSON with keys: ok (true/false), category (one of ok, sexual, minors, self_harm, hate, graphic_violence, doxxing, illegal, unknown), reasons (array).\n"
                        "Be conservative. If unsure, ok=false.\n\n"
                        f"TITLE: {title}\n\nSCRIPT:\n{script_n[:1800]}\n"
                    )
                    resp = ollama_chat(prompt, model=model, temperature=0.0)
                    if resp:
                        m = re.search(r"\{[\s\S]*\}", resp)
                        if m:
                            data = json.loads(m.group(0))
                            ok = bool(data.get("ok", True))
                            cat = str(data.get("category") or "unknown")
                            rs = data.get("reasons") or []
                            if not isinstance(rs, list):
                                rs = [str(rs)]
                            if ok:
                                return SafetyResult(ok=True, reasons=medium_hits, severity="medium", method="ollama", category="ok")
                            return SafetyResult(ok=False, reasons=list(set(medium_hits + [str(x) for x in rs])), severity="medium", method="ollama", category=cat)
        except Exception:
            pass

    # Allow medium flags, but record them for later analysis.
    if medium_hits:
        reasons.extend(medium_hits)
        return SafetyResult(ok=True, reasons=reasons, severity="medium", method="heuristic", category="ok")

    return SafetyResult(ok=True, reasons=[], severity="low", method="heuristic", category="ok")

