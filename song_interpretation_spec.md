# One-Sentence Song Interpretation Spec

## 1) Strict output spec (generation contract)

Use this as a hard validator for each model output.

### Required format
- Exactly **1 sentence**.
- **12–24 words**.
- **First-person voice**: must include `I`, `me`, `my`, or `myself`.
- **Abstractive interpretation**: summarize the narrator’s core inner conflict, realization, or trajectory.
- **No title/artist mentions**.
- **No direct lyric quotation** longer than 3 consecutive words from source lyrics.

### Forbidden style/content
- No opening templates like: `This song is about...`, `The singer feels...`, `The song describes...`.
- No label-only emotion statements (e.g., only naming mood without interpretation).
- No plot spoilers for narrative songs (avoid explicit event reveals if they appear as twists).
- No hedging/meta phrasing: `I think`, `maybe`, `probably`, `it seems`, `the lyrics say`.

### Target quality behavior
- Should infer meaning (theme + perspective), not classify mood.
- Should include at least one concrete angle (relationship dynamic, identity tension, social pressure, memory conflict, etc.).

### Example pass outputs
- `I keep mistaking control for safety, then realizing my loneliness comes from refusing to be truly known.`
- `I turn nostalgia into armor, but each verse admits I’m scared the past is all that still wants me.`

### Example fail outputs
- `This song is about love and heartbreak.`
- `I feel sad and lonely.`
- `The singer is happy but also confused.`

---

## 2) Genericness controls

### A) Banned-word list (exact lowercase match after tokenization)
Use this list to penalize or block outputs when words are used as standalone interpretation crutches.

```text
happy, sad, love, pain, hurt, heartbreak, broken, lonely, anger, angry, fear, afraid,
joy, sorrow, emotional, feelings, relationship, life, struggle, hope, loss, regret,
healing, trauma, darkness, light, good, bad
```

> Implementation note: do **not** hard-fail if one banned word appears with strong specificity; use rule thresholds below.

### B) Generic patterns to detect (regex-like)
Flag output as generic if **any 2+** rules trigger.

1. **Template opener**
   - `^(this song|the song|the singer|the lyrics)\s+(is about|describes|talks about)`

2. **Emotion-only frame**
   - `(i|the singer)\s+(feel|feels|am|is)\s+(very\s+)?(happy|sad|angry|lonely|afraid)`

3. **High banned-word density**
   - `banned_word_count / total_words >= 0.20`

4. **Low lexical diversity**
   - `unique_words / total_words < 0.55`

5. **Too short / too long**
   - `word_count < 12 OR word_count > 24`

6. **No concrete anchor terms**
   - Contains none of: `{memory, mirror, home, silence, body, name, past, future, voice, distance, control, guilt, trust, mask, belonging}`

### C) Genericness score (0–100)
- Start at 100.
- Subtract 20 per triggered rule above.
- Subtract 10 for each banned word beyond the first 2.
- Clamp to [0, 100].
- Suggested gate: reject/regenerate if score < 60.

---

## 3) Human evaluation rubric (1–5)

Rate each output on three dimensions.

### Relevance to lyrics
- **1**: Contradicts lyrics or clearly off-topic.
- **2**: Mentions broad emotion/theme but misses core lyrical content.
- **3**: Generally aligned with lyrics, but partially shallow or mixed.
- **4**: Strongly aligned; captures central theme with minor omissions.
- **5**: Precisely captures central theme and perspective implied by lyrics.

### Specificity (non-generic)
- **1**: Purely generic; could fit almost any song.
- **2**: Slightly specific but mostly cliché emotion labels.
- **3**: Some unique angle; still contains generic phrasing.
- **4**: Clearly song-specific interpretation with concrete nuance.
- **5**: Distinctive, insightful, and tightly grounded in lyrical details.

### Fluency
- **1**: Ungrammatical or hard to understand.
- **2**: Frequent grammar/wording issues.
- **3**: Understandable with minor awkwardness.
- **4**: Natural and clear.
- **5**: Highly polished and concise.

### Optional aggregate
- `overall = 0.4 * relevance + 0.4 * specificity + 0.2 * fluency`

---

## 4) Minimal evaluation set plan (50 songs)

### Dataset composition
Use 50 songs with balanced diversity:
- 10 pop
- 10 hip-hop/rap
- 10 rock/alternative
- 10 R&B/soul
- 10 country/folk

Also balance by era and narrative style:
- ~25 older catalog, ~25 recent.
- At least 15 with clear storytelling arcs.
- At least 15 with metaphor-heavy or ambiguous lyrics.

### Annotation workflow
1. For each song, store full lyrics and metadata.
2. Generate one model interpretation under strict spec.
3. Run automatic genericness checks.
4. Have 2 human raters score (1–5) on the three rubric axes.
5. Adjudicate disagreements >1 point on any axis.

### CSV schema (one row per song output)
```text
song_id,artist,title,genre,year,
model_output,word_count,first_person_pass,single_sentence_pass,
template_opener_flag,emotion_only_flag,banned_word_count,banned_density,
lexical_diversity,anchor_term_flag,generic_rules_triggered,genericness_score,
rater1_relevance,rater1_specificity,rater1_fluency,
rater2_relevance,rater2_specificity,rater2_fluency,
adjudicated_relevance,adjudicated_specificity,adjudicated_fluency,
overall_weighted,notes
```

### Minimum reporting
- Mean and median of each human dimension.
- % outputs passing strict format checks.
- % outputs rejected by genericness gate.
- Correlation between genericness score and human specificity.
