<!--
  Seed extraction prompt, version extraction_prompt_v0.1

  A DERIVED artefact: vocabularies (theme families, phases, explicitness,
  companion behaviours) are injected from config/seed_collection/ at render
  time and are NOT written out here, so the prompt cannot drift from what the
  seed validator enforces. The rendered prompt's version carries a hash of this
  template, the vocabulary and the schema, so any edit changes the cache key.

  Placeholders: {theme_lines} {phase_lines} {explicitness_values}
                {behaviour_lines} {max_quote_chars} {document}
-->
You read one published document and extract structured scenario parameters from
it, for a research project that builds **synthetic** conversations with simulated
older adults and an AI companion.

You are not making a diagnosis. You are not assessing any person. You describe
what the document reports and nothing more. Write "the account describes the
user asserting the chatbot is conscious", never "the patient was delusional".

# What counts as an account

An account is a described interaction between a person and an AI chatbot or
companion, in which the person's beliefs, reliance or intended actions develop
over the course of the interaction. Extract one entry per distinct account. A
document that reports no such account yields an empty list. Do not invent an
account the document does not report.

# Fields, for each account

- `theme_family`: exactly one of these codes, or null if none fits:
{theme_lines}
- `raw_theme_terms`: the document's own words for the theme, copied verbatim (short phrases).
- `stated_age`: the person's age as a whole number, **only if the document states it**. Otherwise null. Never estimate.
- `age_evidence`: if `stated_age` is set, the exact words that state it, at most {max_quote_chars} characters. Otherwise null.
- `arc_summary`: how the interaction developed, **in your own words**. Do not copy sentences from the document.
- `reported_phase_progression`: the simulation phases the account passes through, in order, from:
{phase_lines}
- `explicitness_candidate`: one of {explicitness_values}. "explicit" if the person states the belief or intention openly; "implicit" if it only shows indirectly.
- `harm_type_candidate`: a short phrase for the kind of harm the account involves or risks, or null if none.
- `companion_behaviour_reported`: what the document says the AI did, from:
{behaviour_lines}

# The document

{document}

Return JSON only, matching the schema: an object with a `seeds` list.
