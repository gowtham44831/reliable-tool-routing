# interface dev eval — fictional data, no security cases

Frozen acceptance criteria: >=6/7 valid + D2/D3 exact + D6
correction + no invented fields.

| contract | D1 | D2 | D3 | D4 | D5 | D6 | D7 | total |
|---|---|---|---|---|---|---|---|---|
| A_text_schema | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | 4/7 |
| B_example_contract | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | 7/7 |

A failures: model nested base_url INSIDE params on D1/D2/D7
— a schema-shape ambiguity. Example contract B eliminates it.
Config selected for multistep-pilot-v2: contract B, model
qwen3:14b (unchanged), same episodes/difficulty.