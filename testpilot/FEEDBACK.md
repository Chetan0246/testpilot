# Feedback on Nebius Token Factory and NVIDIA Nemotron

## What I used
- TestPilot is written against the Nebius Token Factory OpenAI-compatible API (default provider).
- Live demo run: NVIDIA API catalog (integrate.api.nvidia.com), same OpenAI-compatible interface, with
  NVIDIA Nemotron 3.5 Lightning 30B-A3B (drafting, triage, repair) and Nemotron 3.5 Super VL 120B-A12B (escalation).

## Zero to hello world
- Token Factory: signing up was quick, but promo credits and API keys only unlock after a card is added.
  As a student in India, my Visa international debit card was rejected by Stripe with
  "Your card does not support this type of purchase", so I could not make a single Token Factory call before the deadline.
- Suggestion: let hackathon participants redeem promo credits without a card (or with UPI / a refundable hold),
  or show which card types are accepted before checkout. This is a real barrier for students outside the US/EU.
- Switching to the NVIDIA API took one environment variable, because both are OpenAI-compatible. First call in under 5 minutes.

## What worked well
- OpenAI compatibility: the same client code runs on both providers.
- Nemotron 3.5 Lightning was strong at test writing: on a module with 3 planted bugs it wrote 13 tests,
  reached 100% line coverage in round 1, and correctly triaged all 3 failures as real code bugs, not test mistakes.
- Full run: 3 model calls, ~17.5k tokens, ~3 minutes end to end.

## What needs work
- Model IDs drift: nemotron-nano-3-30b-a3b and nemotron-3-super-120b-a12b were listed in /v1/models but returned 404 for my account,
  and older Nemotron IDs return 410 (end of life). A clear "available to your account" flag in /v1/models would save time.
- Reasoning models can return content=null with everything in reasoning_content when max_tokens is small; I had to raise max_tokens to 8192.
- With a loose prompt, the first run produced tests with no asserts, so "expected failure" tests passed by accident.
  Requiring an assert in every test fixed it.

## Nano/Lightning vs Super for code generation
- Lightning was enough for drafting and triage on this module; Super only matters when the repair loop gets stuck.
- Lightning is much faster, so it is the right default for an agent loop with several calls.

## Would I build with them again? Why?
- Yes. Nemotron is fast and good at structured test generation, and OpenAI compatibility makes it a drop-in.
  The main fix I'd ask for is card-free access to hackathon credits on Token Factory.
