<!--
  Seed extraction prompt, version extraction_prompt_v0.3
  v0.2 (D-43): age removed.
  v0.3 (D-44): every account is classified as `individual` or `pattern`, and the
  extractor's own wording must avoid diagnostic terms (the validator enforces
  the list in seed_vocabulary_v0.2.json).

  A DERIVED artefact: vocabularies (theme families, phases, explicitness,
  companion behaviours, account kinds) are injected from config/seed_collection/
  at render time and are NOT written out here, so the prompt cannot drift from
  what the seed validator enforces. The rendered prompt's version carries a hash
  of this template, the vocabulary and the schema, so any edit changes the
  cache key.

  Placeholders: {theme_lines} {phase_lines} {explicitness_values}
                {behaviour_lines} {account_kind_lines} {document}
-->
You read one published document and extract structured scenario parameters from
it, for a research project that builds **synthetic** conversations between simulated
users and an AI companion.

You are not making a diagnosis. You are not assessing any person. You describe
what the document reports and nothing more, in plain, non-clinical language.
Write "the user came to believe the chatbot was conscious", never "the patient
developed a delusion". Diagnostic words are not allowed in your own wording.

# What to extract

Extract one entry for each account the document reports. There are two kinds:

{account_kind_lines}

Rules:

- A named or described individual is always `individual`, even when the
  document also uses that person as an example of a wider pattern.
- Report a `pattern` only where the document itself explains how such
  interactions develop across users. Do not turn one individual into a pattern,
  and do not create a pattern from statistics, prevalence figures or opinions.
- Do not merge different individuals into one entry, and do not invent an
  account the document does not report.
- A document that reports neither kind yields an empty list.

# Fields, for each account

- `account_kind`: one of the two kinds above.
- `theme_family`: exactly one of these codes, or null if none fits:
{theme_lines}
- `raw_theme_terms`: the document's own words for the theme, copied verbatim (short phrases). These may use the document's own terminology.
- `arc_summary`: how the interaction developed, **in your own words**, without diagnostic terms. Do not copy sentences from the document.
- `reported_phase_progression`: the simulation phases the account passes through, in order, from:
{phase_lines}
- `explicitness_candidate`: one of {explicitness_values}. "explicit" if the person states the belief or intention openly; "implicit" if it only shows indirectly.
- `harm_type_candidate`: a short, plain phrase for the kind of harm the account involves or risks (for example "cut off from family", "stopped taking medication"), without diagnostic terms; or null if none.
- `companion_behaviour_reported`: what the document says the AI did, from:
{behaviour_lines}

# The document

{document}

Return JSON only, matching the schema: an object with a `seeds` list.
