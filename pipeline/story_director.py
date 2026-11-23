"""
StoryDirector: turns a Reddit post into a family-friendly animated screenplay with a local LLM (Ollama).

It works like a small writers' room:
  1) triage   - rank candidate posts, keep the ones with a real payoff that can stay family-friendly
  2) outline  - facts, hook, cast, beat sheet, payoff, button, viewer question
  3) draft    - screenplay JSON that only uses what the animator kit can render
  4) punch-up - showrunner critique + rule checks, then a revision (up to two rounds)

The screenplay only uses locations/emotions/actions/looks that exist in animator/src/kit.json.
"""
import copy
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .config import KIT_PATH, TRENDS_PATH
from .llm_client import LLMError, OllamaClient

logger = logging.getLogger(__name__)

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,15}$")
TAG_RE = re.compile(r"\[([a-z][a-z \-]{0,24})\]|</?([a-z\-]+)>")

# Grok-era tags in older screenplays -> ElevenLabs audio tags.
LEGACY_INLINE = {
    "laugh": "laughs", "chuckle": "chuckles", "giggle": "giggles", "sigh": "sighs", "cry": "crying",
    "inhale": "gasps", "breath": "sighs", "exhale": "sighs", "tsk": "scoffs",
}
LEGACY_WRAP = {"loud": "shouting", "whisper": "whispers", "soft": "softly"}

GENERIC_PHRASES = [
    "you won't believe", "wait for it", "stay to the end", "wait till the end", "wait until the end",
    "changes everything", "plot twist", "little did i know", "fast forward", "this is crazy",
    "you'll never guess", "buckle up", "let me explain",
]

DEFAULT_SKIN = "#e8b996"
DEFAULT_HAIR = "#3b2a1a"
OUTFIT_PALETTE = ["#4a7bd0", "#e0574f", "#3fa36b", "#f2b134", "#8e5cc7", "#2fb3c4", "#e2779f", "#6b7280"]

SCORE_KEYS = ["hook", "interest", "clarity", "logic", "comedy", "dialogue", "payoff", "ending", "pacing", "visuals"]
MIN_INTEREST = 7

MILD_CURSE_RE = re.compile(r"\b(god ?damn\w*|damn\w*|shit\w*|hell)\b", re.IGNORECASE)
STRONG_CURSE_RE = re.compile(
    r"\b(f+u+c+k\w*|motherf\w*|bitch\w*|ass(hole)?s?|bastards?|dick(head)?s?|piss(ed)?|cunts?|cocks?|"
    r"puss(y|ies)|whores?|sluts?|retard\w*|wtf|stfu)\b",
    re.IGNORECASE,
)


def load_kit(path: str = KIT_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_trends(path: str = TRENDS_PATH, *, fresh_only: bool = True) -> List[Dict[str, Any]]:
    """Trends the writer may reference. A stale list is ignored so old memes don't leak into new videos."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return []
    trends = [t for t in doc.get("trends") or [] if t.get("name")]
    if fresh_only:
        try:
            age = (date.today() - date.fromisoformat(str(doc.get("updated")))).days
        except ValueError:
            return []
        if age > int(doc.get("max_age_days") or 21):
            return []
    return trends


def strip_speech_tags(text: str) -> str:
    """Spoken/caption text without [audio tags] or <wrapping> tags."""
    t = TAG_RE.sub(" ", text or "")
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    return " ".join(t.split()).strip()


def count_words(text: str) -> int:
    return len(strip_speech_tags(text).split())


def screenplay_word_count(screenplay: Dict[str, Any]) -> int:
    return sum(count_words(b.get("text", "")) for s in screenplay.get("scenes", []) for b in s.get("beats", []))


def screenplay_to_script(screenplay: Dict[str, Any]) -> str:
    """Flatten to plain narration text (used for titles, history and the safety filter)."""
    lines = [strip_speech_tags(b.get("text", "")) for s in screenplay.get("scenes", []) for b in s.get("beats", [])]
    return " ".join(x for x in lines if x).strip()


def all_beats(screenplay: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [b for s in screenplay.get("scenes", []) for b in s.get("beats", [])]


@dataclass
class DirectorResult:
    screenplay: Optional[Dict[str, Any]]
    suitable: bool
    reason: str = ""
    warnings: List[str] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)


WRITER_BIBLE = """You write for an animated YouTube Shorts channel that retells real Reddit stories as family-friendly
cartoons (Saturday-morning sitcom energy). Each video is 45-80 seconds, vertical, voiced by actors, with captions.

WORTH WATCHING (most posts are not)
- Only adapt a story a stranger would watch to the end and send to a friend: a clear villain or obstacle who is
  on screen, real stakes, escalation, and a specific, satisfying payoff (the other side visibly loses, gets exposed,
  or has to admit it). A pleasant anecdote with no confrontation ("I asked, the manager said yes") is not enough.

ONLY WHAT'S ON SCREEN
- Viewers only see the characters (outfit, hair, glasses/beard/cap) and the fixed set of each location. Characters
  hold nothing: no bikes, phones, papers, signs, food, gifts or boxes are ever drawn.
- Never point the viewer at something that isn't drawn ("look at this", "she looked down at my bike", "I held up the
  receipt", "I rolled my bike in"). Undrawn things may only come up as off-screen or past facts ("I'd left my bike
  outside"), never as something being looked at or handled in the current shot.
- If the story only works when you can see an undrawn object, it is unsuitable.

WHAT MAKES ONE GREAT
1. Hook (beat 1, narrator, max 12 words): the single most specific, surprising fact of the story, stated plainly.
   Concrete nouns and numbers. Good: "A stranger demanded my employee discount. I don't work there."
   Never clickbait ("you won't believe", "wait for it", "stay to the end", "this changes everything").
2. Setup in at most two beats: who, where, what OP wanted. The audience must understand the normal before the chaos.
3. Show, don't tell. The conflict happens in dialogue between characters on screen. The narrator (OP, first person,
   past tense) only bridges time, adds a funny inner thought, or reacts. At least 45% of beats are in-scene dialogue.
4. Escalate. Every exchange raises the stakes or the absurdity. Every line either moves the story or lands a joke;
   cut anything that does neither.
5. Payoff: the REAL ending from the post, staged on screen, with the other side's reaction visible.
6. Button: one short zinger right after the payoff (a callback to the setup is best).
7. Final beat: the narrator asks viewers ONE question about this story's specific dilemma, never a generic "thoughts?".

CRAFT
- Logic first: every line must make sense for the character saying it, with what they know at that moment.
  No contradictions, no character suddenly knowing things, no muddled cause and effect.
- Each character has one clear want and a recognizable way of talking (the entitled one is over-confident,
  the tired employee is dry and polite, the kid is blunt).
- Comedy comes from specifics, contrast (calm narrator vs. chaos on screen), rule of three, and callbacks.
- Written to be spoken: short sentences, contractions, 3-15 words per sentence, max 25 words per beat.
  No stage directions or emojis inside spoken text. Never say "Reddit", "OP", "upvotes" or "AITA" in dialogue.
- Keep the real events and the real ending. Tighten and dramatize; do not invent new twists or change who was right.
- Trends: if a current trend from the provided list fits naturally, use at most one, in a single side line (a narrator
  aside, a comparison, a character's excuse, or the button). It never goes in the hook and never changes what
  happened, who was right, or the ending. If nothing fits, use none; a forced reference is worse than none.

LANGUAGE
- Clean by default. Very rarely, when a moment is genuinely absurd and the mood is funny or dramatic, ONE mild,
  funny curse is allowed, said as a reaction rather than an insult: "Shit, bro." / "God damn, this guy." Most videos
  have none. Only shit, damn, god damn or hell; never in the title, the hook, the first three beats or the final
  question; never from or at a kid. No f-word, slurs, sexual words, innuendo or name-calling.

FAMILY-FRIENDLY
- No real names, usernames, employers, schools or towns from the post; use roles or common first names.
- Unsuitable (reject): sexual content, self-harm, abuse, serious injury or violence, drugs, crime how-tos, hate,
  medical tragedy, death, posts that are updates/part 2/have no ending, or stories that only work with adult content.
"""


class StoryDirector:
    def __init__(self, client: Optional[OllamaClient] = None, kit: Optional[Dict[str, Any]] = None,
                 think: bool = True):
        self.client = client or OllamaClient()
        self.kit = kit or load_kit()
        # Let the model reason before planning/critique (slower, noticeably better jokes and logic).
        self.think = think

    # ----------------------------
    # Schemas
    # ----------------------------
    def schema(self) -> Dict[str, Any]:
        k = self.kit
        shots = "|".join(k["shots"])
        look = {
            "type": "object",
            "properties": {
                "hair": {"type": "string", "enum": k["hairStyles"]},
                "hairColor": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "skin": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "outfit": {"type": "string", "enum": k["outfits"]},
                "outfitColor": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$"},
                "accessory": {"type": "string", "enum": k["accessories"]},
            },
            "required": ["hair", "hairColor", "skin", "outfit", "outfitColor", "accessory"],
            "additionalProperties": False,
        }
        character = {
            "type": "object",
            "properties": {
                "id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,15}$"},
                "name": {"type": "string", "maxLength": 24},
                "gender": {"type": "string", "enum": k["genders"]},
                "age": {"type": "string", "enum": k["ages"]},
                "voiceTone": {"type": "string", "enum": k["voiceTones"]},
                "look": look,
            },
            "required": ["id", "name", "gender", "age", "voiceTone", "look"],
            "additionalProperties": False,
        }
        beat = {
            "type": "object",
            "properties": {
                "speaker": {"type": "string"},
                "text": {"type": "string", "maxLength": 220},
                "emotion": {"type": "string", "enum": k["emotions"]},
                "action": {"type": "string", "enum": k["actions"]},
                "camera": {"type": "string", "pattern": f"^({shots})(:[a-z][a-z0-9_]{{0,15}})?$"},
            },
            "required": ["speaker", "text", "emotion", "action", "camera"],
            "additionalProperties": False,
        }
        scene = {
            "type": "object",
            "properties": {
                "location": {"type": "string", "enum": k["locations"]},
                "timeOfDay": {"type": "string", "enum": k["timesOfDay"]},
                "onscreen": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": k["maxCharacters"]},
                "beats": {"type": "array", "items": beat, "minItems": 1, "maxItems": 12},
            },
            "required": ["location", "timeOfDay", "onscreen", "beats"],
            "additionalProperties": False,
        }
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 90},
                "mood": {"type": "string", "enum": k["moods"]},
                "characters": {"type": "array", "items": character, "minItems": 1, "maxItems": k["maxCharacters"]},
                "scenes": {"type": "array", "items": scene, "minItems": 1, "maxItems": 6},
            },
            "required": ["title", "mood", "characters", "scenes"],
            "additionalProperties": False,
        }

    def _outline_schema(self) -> Dict[str, Any]:
        k = self.kit
        return {
            "type": "object",
            "properties": {
                "suitable": {"type": "boolean"},
                "rejectReason": {"type": "string"},
                "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                "logline": {"type": "string"},
                "hook": {"type": "string"},
                "mood": {"type": "string", "enum": k["moods"]},
                "cast": {
                    "type": "array",
                    "maxItems": k["maxCharacters"],
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "want": {"type": "string"},
                            "voice": {"type": "string"},
                        },
                        "required": ["id", "name", "role", "want", "voice"],
                        "additionalProperties": False,
                    },
                },
                "beats": {
                    "type": "array",
                    "maxItems": 12,
                    "items": {
                        "type": "object",
                        "properties": {
                            "purpose": {"type": "string", "enum": ["hook", "tease", "setup", "escalation", "turn", "payoff", "button", "question"]},
                            "location": {"type": "string", "enum": k["locations"]},
                            "summary": {"type": "string"},
                            "joke": {"type": "string"},
                        },
                        "required": ["purpose", "location", "summary", "joke"],
                        "additionalProperties": False,
                    },
                },
                "button": {"type": "string"},
                "question": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["suitable", "rejectReason", "facts", "logline", "hook", "mood", "cast", "beats", "button", "question", "title"],
            "additionalProperties": False,
        }

    @staticmethod
    def _critique_schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "object",
                    "properties": {key: {"type": "integer", "minimum": 1, "maximum": 10} for key in SCORE_KEYS},
                    "required": SCORE_KEYS,
                    "additionalProperties": False,
                },
                "fixes": {
                    "type": "array",
                    "maxItems": 10,
                    "items": {
                        "type": "object",
                        "properties": {
                            "line": {"type": "string"},
                            "problem": {"type": "string"},
                            "rewrite": {"type": "string"},
                        },
                        "required": ["line", "problem", "rewrite"],
                        "additionalProperties": False,
                    },
                },
                "verdict": {"type": "string", "enum": ["ship", "revise"]},
            },
            "required": ["scores", "fixes", "verdict"],
            "additionalProperties": False,
        }

    # ----------------------------
    # Prompts
    # ----------------------------
    def _set_list(self) -> str:
        dressing = self.kit.get("setDressing") or {}
        lines = [f"  {loc}: {dressing[loc]}" for loc in self.kit["locations"] if dressing.get(loc)]
        return "- What each location shows (nothing else is drawn, and characters hold nothing):\n" + "\n".join(lines) + "\n"

    @staticmethod
    def _trend_rules() -> str:
        trends = load_trends()
        if not trends:
            return ""
        lines = ["CURRENT TRENDS (optional; at most one, only where it fits this story naturally):"]
        for t in trends:
            example = (t.get("examples") or [""])[0]
            lines.append(f"- {t['name']}: {t.get('what', '')} Fits: {t.get('fits', '')}. Example: \"{example}\"")
        return "\n".join(lines) + "\n"

    def _staging_rules(self) -> str:
        k = self.kit
        tags = ", ".join(f"[{t}]" for t in k["speechTags"]["inline"])
        return (
            "STAGING (the animation system can only render these):\n"
            f"- 2-5 scenes. Locations ONLY: {', '.join(k['locations'])}. timeOfDay: {', '.join(k['timesOfDay'])}. "
            "Change scene only when the story changes place or time.\n"
            + self._set_list() +
            f"- At most {k['maxCharacters']} characters including 'op' (the original poster). Ids are short lowercase "
            "(op, mom, boss, karen). speaker is 'narrator' or a character id.\n"
            "- onscreen lists the character ids visible in a scene (1-4); every in-scene speaker must be onscreen.\n"
            "- emotion/action describe the speaker (for narrator beats: OP's on-screen reaction).\n"
            f"  emotions: {', '.join(k['emotions'])}. actions: {', '.join(k['actions'])}.\n"
            "- camera: 'wide' to establish, 'closeup:<id>' for punchlines/reactions, 'two_shot' for arguments, "
            "'push_in:<id>' for tension, 'shake:<id>' for shocks. Mostly closeups and two_shots (vertical phone screen).\n"
            "- Looks: realistic skin hex, natural hair hex, clearly different saturated outfit colors per character. "
            f"hair: {', '.join(k['hairStyles'])}; outfits: {', '.join(k['outfits'])}; accessories: {', '.join(k['accessories'])}.\n"
            "- voiceTone matches personality; if OP's gender isn't stated, pick what fits the post.\n"
            f"- Voice-acting tags allowed inside text: {tags}. At most one per beat, 3-6 per video, only where the "
            "delivery matters (a gasp before a shock, sarcasm on a zinger).\n"
        )

    def _length_rules(self, min_words: int, max_words: int, tease: Optional[str], question: Optional[str]) -> str:
        out = f"- Total spoken words across all beats: {min_words}-{max_words}.\n"
        if tease:
            out += f"- Beat 2 is a one-line narrator tease. Style: {tease}\n"
        else:
            out += "- No tease line: go straight from the hook into the setup.\n"
        if question:
            out += f"- Final viewer question style: {question}\n"
        return out

    @staticmethod
    def _post_prompt(trend_data: Dict[str, Any]) -> str:
        title = (trend_data.get("title") or "").strip()
        sub = (trend_data.get("subreddit") or "").strip()
        body = (trend_data.get("text") or trend_data.get("description") or "").strip()
        body = re.sub(r"http\S+|www\.\S+", "", body)
        if len(body) > 6000:
            body = body[:6000].rsplit(" ", 1)[0] + " ..."
        return f"SUBREDDIT: r/{sub}\nTITLE: {title}\n\nPOST:\n{body}"

    # ----------------------------
    # Pass 1: triage
    # ----------------------------
    def pick_stories(self, candidates: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], int, str]]:
        """Rank candidate posts; returns [(trend_data, score, reason)] best first, unsuitable ones removed."""
        if not candidates:
            return []
        schema = {
            "type": "object",
            "properties": {
                "ranking": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "family_friendly": {"type": "boolean"},
                            "has_payoff": {"type": "boolean"},
                            "score": {"type": "integer", "minimum": 1, "maximum": 10},
                            "reason": {"type": "string"},
                        },
                        "required": ["index", "family_friendly", "has_payoff", "score", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["ranking"],
            "additionalProperties": False,
        }
        posts = []
        for i, c in enumerate(candidates):
            body = re.sub(r"\s+", " ", (c.get("text") or c.get("description") or ""))[:1400]
            posts.append(f"[{i}] r/{c.get('subreddit', '')} | {c.get('title', '')}\n{body}")
        system = (
            WRITER_BIBLE
            + "\nYou are picking which posts to adapt next. For each post decide: can it be told family-friendly "
            "without changing what happened (family_friendly), does it have a clear, satisfying ending (has_payoff), "
            "and score 1-10 how good a 60-second cartoon it makes. Score as a stranger scrolling past: would they "
            "stop, watch to the end and comment? Great ones have a hook you can say in one line, a clear antagonist "
            "who appears in the story, escalation, a payoff with a visible reaction, few characters and everyday "
            "places. A mild anecdote with no confrontation is a 3-5. A story whose point is an object we can't draw "
            "(only people and fixed rooms are drawn) is 4 or less. Be strict: most posts are a 4-6; only great ones "
            "get 8+."
        )
        raw = self.client.chat_json(
            schema,
            [{"role": "system", "content": system}, {"role": "user", "content": "\n\n".join(posts)}],
            schema_name="triage", temperature=0.2, model=self.client.fast_model, think=False, num_predict=3000,
        )
        out: List[Tuple[Dict[str, Any], int, str]] = []
        seen = set()
        for r in raw.get("ranking") or []:
            i = r.get("index")
            if not isinstance(i, int) or not 0 <= i < len(candidates) or i in seen:
                continue
            seen.add(i)
            if r.get("family_friendly") and r.get("has_payoff"):
                out.append((candidates[i], int(r.get("score") or 0), str(r.get("reason") or "")))
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    # ----------------------------
    # Pass 2-4: outline, draft, punch-up
    # ----------------------------
    def outline(self, trend_data: Dict[str, Any], *, tease: Optional[str], question: Optional[str],
                min_words: int, max_words: int) -> Dict[str, Any]:
        system = (
            WRITER_BIBLE
            + "\nTASK: break the post down before anyone writes dialogue.\n"
            "- suitable: decide first (not worth watching, or only works with an undrawn object on screen, means "
            "false); if false give rejectReason and keep the other fields minimal.\n"
            "- facts: the real events in order, as short plain sentences.\n"
            "- hook: the exact beat-1 line (max 12 words).\n"
            "- cast: id 'op' for the poster plus up to 3 others; want = what they're after; voice = how they talk.\n"
            "- beats: the beat sheet in order (hook, optional tease, setup, 2-4 escalation beats, turn, payoff, "
            "button, question), each with where it happens and the joke or tension it carries.\n"
            "- button: the zinger after the payoff. question: the specific final question for viewers.\n"
            "- title: a YouTube title under 70 characters, specific and curiosity-driven, no clickbait words.\n"
            + self._length_rules(min_words, max_words, tease, question)
            + self._set_list()
            + self._trend_rules()
        )
        return self.client.chat_json(
            self._outline_schema(),
            [{"role": "system", "content": system}, {"role": "user", "content": self._post_prompt(trend_data)}],
            schema_name="outline", temperature=0.8, think=self.think, num_predict=12000,
        )

    def _draft_messages(self, trend_data: Dict[str, Any], outline: Dict[str, Any], min_words: int, max_words: int,
                        tease: Optional[str], question: Optional[str]) -> List[Dict[str, str]]:
        system = (
            WRITER_BIBLE + "\n" + self._staging_rules()
            + "LENGTH AND SHAPE:\n" + self._length_rules(min_words, max_words, tease, question)
            + "- Beat 1 is the hook (narrator). The final beat is the narrator's viewer question.\n"
            "- Follow the outline, but write every line fresh and funny; keep each beat to 1-2 short sentences.\n"
            + self._trend_rules()
        )
        user = (
            self._post_prompt(trend_data)
            + "\n\nOUTLINE (from the writers' room):\n" + json.dumps(outline, ensure_ascii=False)
            + "\n\nWrite the full screenplay JSON."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def critique(self, trend_data: Dict[str, Any], screenplay: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            WRITER_BIBLE
            + "\nYou are the showrunner doing a table read. Score the screenplay 1-10 on: hook (would a scroller "
            "stop?), interest (would a stranger watch to the end and comment? a mild anecdote is a 4), clarity "
            "(does someone who never read the post follow it?), logic (every line makes sense for its speaker), "
            "comedy (real laughs or gasps, not filler), dialogue (distinct, natural voices), payoff (the real ending "
            "lands with a visible reaction), ending (button + specific question), pacing (no wasted lines), visuals "
            "(no line points at or handles anything that isn't drawn; a forced trend reference or a curse that "
            "doesn't fit also costs points here). Then list the most important concrete fixes: quote the exact line, "
            "say what's wrong, and give the rewritten line. verdict=ship only if every score is 8 or higher.\n"
            + self._set_list()
            + self._trend_rules()
        )
        user = self._post_prompt(trend_data) + "\n\nSCREENPLAY:\n" + json.dumps(screenplay, ensure_ascii=False)
        return self.client.chat_json(
            self._critique_schema(),
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            schema_name="critique", temperature=0.3, think=self.think, num_predict=10000,
        )

    def rule_problems(self, screenplay: Dict[str, Any], min_words: int, max_words: int,
                      tease: Optional[str] = None) -> List[str]:
        """Checks that don't need a model."""
        problems: List[str] = []
        beats = all_beats(screenplay)
        if not beats:
            return ["no beats"]
        words = screenplay_word_count(screenplay)
        if not (min_words * 0.85 <= words <= max_words * 1.1):
            problems.append(f"total spoken words is {words}, must be {min_words}-{max_words}")
        first = beats[0]
        if first.get("speaker") != "narrator" or count_words(first["text"]) > 14:
            problems.append("beat 1 must be a narrator hook of at most 12 words")
        last = beats[-1]
        if last.get("speaker") != "narrator" or not strip_speech_tags(last["text"]).endswith("?"):
            problems.append("the final beat must be the narrator asking viewers one specific question")
        dialogue = sum(1 for b in beats if b.get("speaker") != "narrator")
        if dialogue / len(beats) < 0.4:
            problems.append(f"only {dialogue} of {len(beats)} beats are in-scene dialogue; dramatize more of the "
                            "story as lines spoken by characters instead of narration")
        run = 0
        for b in beats:
            run = run + 1 if b.get("speaker") == "narrator" else 0
            if run == 3:
                problems.append("three narrator beats in a row; turn one into dialogue or cut it")
                break
        for b in beats:
            n = count_words(b["text"])
            if n > 30:
                problems.append(f"line too long ({n} words): {strip_speech_tags(b['text'])[:60]}...")
        text = screenplay_to_script(screenplay).lower()
        for p in GENERIC_PHRASES:
            if p in text and not (tease and p in tease.lower()):
                problems.append(f"remove the generic phrase '{p}'")
        tags = sum(len(TAG_RE.findall(b["text"])) for b in beats)
        if tags > 8:
            problems.append(f"{tags} voice tags is too many; keep 3-6 where delivery matters")

        ages = {c.get("id"): c.get("age") for c in screenplay.get("characters") or []}
        curses = 0
        for i, b in enumerate(beats):
            spoken = strip_speech_tags(b["text"])
            if STRONG_CURSE_RE.search(spoken):
                problems.append(f"strong or off-list profanity is never allowed: {spoken[:60]}")
            found = len(MILD_CURSE_RE.findall(spoken))
            if not found:
                continue
            curses += found
            if i < 3 or i == len(beats) - 1:
                problems.append("no cursing in the first three beats or the final question")
            if ages.get(b.get("speaker")) == "kid":
                problems.append("kids never curse")
        if curses > 1:
            problems.append(f"{curses} curse words; at most one per video, and most videos have none")
        title = str(screenplay.get("title") or "")
        if MILD_CURSE_RE.search(title) or STRONG_CURSE_RE.search(title):
            problems.append("no cursing in the title")

        hook = strip_speech_tags(first["text"]).lower()
        used = [t for t in load_trends(fresh_only=False) if any(m in text for m in t.get("match") or [])]
        if len(used) > 1:
            problems.append(f"use at most one trend reference per video (found {', '.join(t['name'] for t in used)})")
        if any(m in hook for t in used for m in t.get("match") or []):
            problems.append("keep trend references out of the hook; the hook is the story's own most surprising fact")
        return problems

    def revise(self, trend_data: Dict[str, Any], screenplay: Dict[str, Any], fixes: List[Dict[str, Any]],
               problems: List[str], min_words: int, max_words: int, tease: Optional[str],
               question: Optional[str]) -> Optional[Dict[str, Any]]:
        notes = [f"- {p}" for p in problems]
        for f in fixes:
            notes.append(f"- \"{f.get('line', '')}\": {f.get('problem', '')} -> {f.get('rewrite', '')}")
        system = (
            WRITER_BIBLE + "\n" + self._staging_rules()
            + "LENGTH AND SHAPE:\n" + self._length_rules(min_words, max_words, tease, question)
            + "\nYou are revising after the table read. Apply every note, keep what already works, and return the "
            "complete revised screenplay JSON.\n"
            + self._trend_rules()
        )
        user = (
            self._post_prompt(trend_data)
            + "\n\nCURRENT SCREENPLAY:\n" + json.dumps(screenplay, ensure_ascii=False)
            + "\n\nNOTES:\n" + "\n".join(notes)
        )
        raw = self.client.chat_json(
            self.schema(), [{"role": "system", "content": system}, {"role": "user", "content": user}],
            schema_name="screenplay", temperature=0.5, think=False,
        )
        fixed, blocking, _ = self.validate(raw)
        if not fixed or blocking:
            logger.warning(f"Revision invalid: {blocking}")
            return None
        return fixed

    # ----------------------------
    # Public API
    # ----------------------------
    def direct(self, trend_data: Dict[str, Any], *, min_words: int = 170, max_words: int = 230,
               tease: Optional[str] = None, question: Optional[str] = None, rounds: int = 2) -> DirectorResult:
        try:
            outline = self.outline(trend_data, tease=tease, question=question, min_words=min_words, max_words=max_words)
        except LLMError as e:
            return DirectorResult(None, False, f"llm_error: {e}")
        if not outline.get("suitable", False):
            return DirectorResult(None, False, str(outline.get("rejectReason") or "unsuitable"))

        messages = self._draft_messages(trend_data, outline, min_words, max_words, tease, question)
        screenplay: Optional[Dict[str, Any]] = None
        warnings: List[str] = []
        for attempt in range(2):
            try:
                raw = self.client.chat_json(self.schema(), messages, schema_name="screenplay", temperature=0.7, think=False)
            except LLMError as e:
                return DirectorResult(None, False, f"llm_error: {e}")
            screenplay, blocking, warnings = self.validate(raw)
            if screenplay and not blocking:
                break
            logger.warning(f"Draft {attempt + 1} invalid: {blocking}")
            messages = messages + [
                {"role": "assistant", "content": json.dumps(raw)},
                {"role": "user", "content": "Fix these problems and return the full corrected screenplay:\n- " + "\n- ".join(blocking)},
            ]
            screenplay = None
        if not screenplay:
            return DirectorResult(None, False, "invalid_screenplay", warnings)

        history: List[Dict[str, Any]] = []
        for rnd in range(rounds):
            problems = self.rule_problems(screenplay, min_words, max_words, tease)
            try:
                review = self.critique(trend_data, screenplay)
            except LLMError as e:
                logger.warning(f"Critique failed ({e}); keeping the current draft")
                break
            scores = review.get("scores") or {}
            history.append({"round": rnd + 1, "scores": scores, "rule_problems": problems})
            logger.info(f"Table read {rnd + 1}: {scores} rule_problems={len(problems)}")
            if not problems and review.get("verdict") == "ship" and min(scores.values() or [0]) >= 8:
                break
            try:
                revised = self.revise(trend_data, screenplay, review.get("fixes") or [], problems,
                                      min_words, max_words, tease, question)
            except LLMError as e:
                logger.warning(f"Revision failed ({e}); keeping the current draft")
                break
            if revised:
                screenplay = revised

        interest = [int(h["scores"].get("interest") or 0) for h in history if h.get("scores")]
        if interest and max(interest) < MIN_INTEREST:
            return DirectorResult(None, False, f"not_interesting ({max(interest)}/10)", warnings,
                                  notes={"outline": outline, "table_reads": history})

        if not screenplay.get("title") and outline.get("title"):
            screenplay["title"] = str(outline["title"])[:90]
        remaining = self.rule_problems(screenplay, min_words, max_words, tease)
        return DirectorResult(screenplay, True, "", warnings + remaining,
                              notes={"outline": outline, "table_reads": history})

    def shorten(self, screenplay: Dict[str, Any], target_words: int) -> Optional[Dict[str, Any]]:
        """Tighten an existing screenplay to ~target_words, keeping cast, scenes and ending."""
        system = (
            WRITER_BIBLE + "\n" + self._staging_rules()
            + f"\nYou edit for time. Tighten the given screenplay to about {target_words} total spoken words. Keep the "
            "same characters, looks and scene order, the hook, the payoff, the button and the final question. "
            "Cut filler and narration first; merge beats; never add new content."
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(screenplay)}]
        try:
            raw = self.client.chat_json(self.schema(), messages, schema_name="screenplay", temperature=0.3, think=False)
        except LLMError as e:
            logger.error(f"Screenplay shorten failed: {e}")
            return None
        fixed, problems, _ = self.validate(raw)
        if not fixed or problems:
            logger.warning(f"Shortened screenplay invalid: {problems}")
            return None
        return fixed

    # ----------------------------
    # Validation / normalization
    # ----------------------------
    def validate(self, raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
        """Returns (normalized screenplay, blocking problems, non-blocking warnings)."""
        k = self.kit
        problems: List[str] = []
        warnings: List[str] = []
        sp = copy.deepcopy(raw or {})

        chars: List[Dict[str, Any]] = []
        seen = set()
        for i, c in enumerate(sp.get("characters") or []):
            cid = str(c.get("id") or "").strip().lower()
            if not ID_RE.match(cid) or cid in seen or cid == "narrator":
                warnings.append(f"dropped character with bad/duplicate id {cid!r}")
                continue
            seen.add(cid)
            look = c.get("look") or {}
            norm_look = {
                "hair": look.get("hair") if look.get("hair") in k["hairStyles"] else "short",
                "hairColor": look.get("hairColor") if HEX_RE.match(str(look.get("hairColor") or "")) else DEFAULT_HAIR,
                "skin": look.get("skin") if HEX_RE.match(str(look.get("skin") or "")) else DEFAULT_SKIN,
                "outfit": look.get("outfit") if look.get("outfit") in k["outfits"] else "tshirt",
                "outfitColor": look.get("outfitColor") if HEX_RE.match(str(look.get("outfitColor") or "")) else OUTFIT_PALETTE[i % len(OUTFIT_PALETTE)],
                "accessory": look.get("accessory") if look.get("accessory") in k["accessories"] else "none",
            }
            chars.append({
                "id": cid,
                "name": str(c.get("name") or cid.title())[:24],
                "gender": c.get("gender") if c.get("gender") in k["genders"] else "female",
                "age": c.get("age") if c.get("age") in k["ages"] else "20s",
                "voiceTone": c.get("voiceTone") if c.get("voiceTone") in k["voiceTones"] else "warm",
                "look": norm_look,
            })
        if not any(c["id"] == "op" for c in chars):
            problems.append("no character with id 'op' (the original poster)")
        if len(chars) > k["maxCharacters"]:
            problems.append(f"too many characters ({len(chars)}), max {k['maxCharacters']}")
            chars = chars[: k["maxCharacters"]]
        ids = {c["id"] for c in chars}

        scenes: List[Dict[str, Any]] = []
        for s in sp.get("scenes") or []:
            onscreen = [x for x in (s.get("onscreen") or []) if x in ids]
            beats: List[Dict[str, Any]] = []
            for b in s.get("beats") or []:
                text = self._clean_text(str(b.get("text") or ""))
                if not strip_speech_tags(text):
                    continue
                speaker = str(b.get("speaker") or "narrator").strip().lower()
                if speaker != "narrator" and speaker not in ids:
                    warnings.append(f"unknown speaker {speaker!r} -> narrator")
                    speaker = "narrator"
                if speaker != "narrator" and speaker not in onscreen:
                    if len(onscreen) < k["maxCharacters"]:
                        onscreen.append(speaker)
                    else:
                        problems.append(f"speaker {speaker!r} is not onscreen in a full scene")
                shot, focus = self._parse_camera(str(b.get("camera") or "wide"))
                subject = speaker if speaker != "narrator" else ("op" if "op" in ids else None)
                if focus and focus not in ids:
                    focus = None
                if shot in ("closeup", "push_in", "shake") and not focus:
                    focus = subject if subject in onscreen else (onscreen[0] if onscreen else None)
                beats.append({
                    "speaker": speaker,
                    "text": text,
                    "emotion": b.get("emotion") if b.get("emotion") in k["emotions"] else "neutral",
                    "action": b.get("action") if b.get("action") in k["actions"] else "talk",
                    "camera": f"{shot}:{focus}" if focus else shot,
                })
            if not beats:
                continue
            if not onscreen:
                onscreen = ["op"] if "op" in ids else list(ids)[:1]
            scenes.append({
                "location": s.get("location") if s.get("location") in k["locations"] else "living_room",
                "timeOfDay": s.get("timeOfDay") if s.get("timeOfDay") in k["timesOfDay"] else "day",
                "onscreen": onscreen[: k["maxCharacters"]],
                "beats": beats,
            })
        if not scenes:
            problems.append("no scenes with spoken beats")

        out = {
            "title": strip_speech_tags(str(sp.get("title") or "")).strip()[:90],
            "mood": sp.get("mood") if sp.get("mood") in k["moods"] else "funny",
            "characters": chars,
            "scenes": scenes,
        }
        if not out["title"] and scenes:
            out["title"] = strip_speech_tags(scenes[0]["beats"][0]["text"])[:90]
        return out, problems, warnings

    def _parse_camera(self, cam: str) -> Tuple[str, Optional[str]]:
        shot, _, focus = cam.strip().lower().partition(":")
        if shot not in self.kit["shots"]:
            shot = "wide"
        return shot, (focus or None)

    def _clean_text(self, text: str) -> str:
        """Keep only whitelisted voice tags (legacy Grok tags are converted); drop the rest."""
        allowed = set(self.kit["speechTags"]["inline"])

        def wrap(m: "re.Match[str]") -> str:
            tag = LEGACY_WRAP.get(m.group(1))
            return f"[{tag}] {m.group(2)}" if tag in allowed else m.group(2)

        t = re.sub(r"<([a-z\-]+)>(.*?)</\1>", wrap, text or "")

        def repl(m: "re.Match[str]") -> str:
            inline = m.group(1)
            if not inline:
                return " "
            inline = LEGACY_INLINE.get(inline.strip(), inline.strip())
            return f"[{inline}]" if inline in allowed else " "

        t = TAG_RE.sub(repl, t)
        t = re.sub(r"\s+([,.!?;:])", r"\1", " ".join(t.split()))
        return t.strip()


def main() -> None:
    """Write a screenplay for one Reddit post (URL) or a saved trend JSON, without voicing or rendering."""
    import argparse

    from .reddit_fetcher import RedditFetcher

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    p = argparse.ArgumentParser(description="Write a screenplay with the local LLM")
    p.add_argument("--story-url", help="Reddit post URL")
    p.add_argument("--trend-json", help="JSON file with title/subreddit/text")
    p.add_argument("--out", default="screenplay_draft.json")
    p.add_argument("--no-think", action="store_true", help="Faster, skips model reasoning")
    args = p.parse_args()
    if args.story_url:
        trend = RedditFetcher().fetch_story_by_url(args.story_url)
    elif args.trend_json:
        with open(args.trend_json, "r", encoding="utf-8") as f:
            trend = json.load(f)
    else:
        p.error("--story-url or --trend-json is required")
    if not trend:
        raise SystemExit("could not load the story")
    director = StoryDirector(think=not args.no_think)
    if not director.client.ready():
        raise SystemExit(f"Ollama model {director.client.model!r} is not available (ollama pull {director.client.model})")
    res = director.direct(trend, tease="hint at the payoff without revealing it, specific to this story",
                          question="ask viewers to judge OP's specific choice")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"source": trend, "screenplay": res.screenplay, "result": {"suitable": res.suitable, "reason": res.reason,
                   "warnings": res.warnings, "notes": res.notes}}, f, indent=1, ensure_ascii=False)
    print(f"suitable={res.suitable} reason={res.reason!r} words={screenplay_word_count(res.screenplay or {})} -> {args.out}")


if __name__ == "__main__":
    main()
