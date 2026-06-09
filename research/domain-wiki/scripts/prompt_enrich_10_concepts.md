# Enrichment Prompt: Ch10 concepts.yaml

## Current State
- Existing concepts: 2 (产品电气设计原则, 产品安全性与可靠性)
- Existing KE: 1 (产品电气装配工艺)
- Existing entity: 1 (汇流排（铜排）)
- Pipeline status: ALL pending

## Source Analysis (第10章 产品的电气设计和装配, 28KB)

The chapter has these major content sections NOT yet covered as concepts:

### §10.2 元器件、电气配件的排布和安装 (lines 16-38, ~23 lines dense content)
16 detailed rules covering: heavy component placement at bottom, vertical mounting of contactors/relays, heat sink/silicon grease, control relays on edges, easy-access fault components, vibration damping, operator ergonomics (1.3-1.5m height), indicator lights, lightning protection modules, fuse holders, EMC-sensitive component isolation, transformer-proximity routing, vertical electrolytic capacitors, user terminal blocks at 30cm height, copper fasteners.
- Supporting materials: none within section
- Type: method-type (装配规范)

### §10.3.1 排布导线注意事项 (lines 49-80, ~32 lines)
18 detailed rules covering: no wire contact with metal edges (rubber grommets), shortest routes with right-angle bends, HV/LV separation, max 30 wires per 1.5mm² bundle, twisted phase wires, no shielding wire crossover, heat-source distance (表10-1), vertical switch wiring, HV/LV/AC/DC/power/signal separation, cable trays >150mm apart, stress support for cables, crimp terminals with heat-shrink, single wire per terminal max 2, stranded wire crimping, door-hinge cable slack, voltage-rated insulation, EMC loop minimization, copper bar connections.
- Supporting materials: 表10-1 (发热元件间距)
- Type: method-type (布线规范)

### §10.3.2 汇流排的设计安装 (lines 82-101, ~20 lines)
8 rules: Cu/Al current density (4/3 A/mm² at 25°C), temperature derating 5%/5°C rise, surface finish (tin/nickel), conductive adhesive, phase sequence rules (上A中B下C), support every 0.5-1m, ≥2cm spacing, cross-section area preservation.
- Supporting materials: current density formula
- Already covered as entity "汇流排（铜排）"

### EMC Section: 电磁骚扰与防护 (lines 153-183, ~31 lines)
EMC wiring protection: shield sensitive/noisy devices, power/signal/control line separation (mutual interference), field strength decay with distance, grouping same-direction wires, shielded cable grounding rules (single-end for analog low-freq, dual-end for digital/high-freq), ground classification (power/ chassis/digital/analog/total ground), non-magnetic bolts for inductors, Hall sensor/HVV placement away from interference, surge/lightning protection at power entry.
- Supporting materials: 图10-1 (屏蔽线接地处理)
- Type: method-type (EMC防护)

### §10.5 机柜间电缆的处理 (lines 191-230, ~40 lines)
10 rules: single-side cable entry, redundant ground wires, noise/sensitive cable separation (right-angle crossing), signal type grouping (analog/digital in separate shielded bundles), long-distance cables in grounded metal trays, very sensitive cables in separate steel pipe, tray covers, connector pin layout (analog/digital grouped with 0V between), signal+return loop minimization, chassis grounding avoiding ground loops (图10-2).
- Supporting materials: 图10-2 (机柜接地处理)
- Type: method-type (电缆处理)

## New Concepts to Add

### Concept 3: 元器件排布与装配规范
- **Source**: §10.2 (lines 16-38)
- **Type**: Method-type (装配规范)
- **Key content**: 16 rules for component layout, heavy component placement, vibration isolation, thermal management, ergonomics, accessibility
- **Supporting materials**: none directly in section but substantial standalone method content
- **Name**: Must be noun phrase

### Concept 4: 导线排布与布线规范
- **Source**: §10.3.1 (lines 49-80) + §10.3.2 current density formula context
- **Type**: Method-type (布线规范)
- **Key content**: 18 wire routing rules, cable management, terminal connections, heat-source clearance
- **Supporting materials**: 表10-1 (发热元件与导线间距), current density formula
- **Note**: §10.3.2 busbar content already in entities.yaml — include only the wire routing EMC aspect

### Concept 5: 电磁骚扰布线防护
- **Source**: EMC section within §10.4 (lines 153-183) + §10.5 (lines 191-230)
- **Type**: Method-type (EMC防护)
- **Key content**: shielded cable grounding (single-end/dual-end), cable classification, ground type differentiation, inter-cabinet cable handling, ground loop avoidance
- **Supporting materials**: 图10-1 (屏蔽线接地处理), 图10-2 (机柜接地处理)

## YAML Format Requirements
- Each concept is a list item with: name, file, fm (confidence, source_chapter, source_from, confidence_note), bd (all body fields)
- Body fields (bd) must follow the v6.1 spec:
  - definition_sentence: > format, text from source
  - term_english: English term
  - term_definition: expanded definition (1-3 sentences)
  - domain: 电磁兼容/产品设计/...
  - tech_classification: technical classification
  - classification: 电磁兼容领域/产品设计/...
  - application_scenarios: scenario descriptions (≥3 for method-type, each ≥50 chars)
  - typical_systems: wikilinks to related systems
  - structure: ≥100 chars, detailed structure
  - core_concept_map: Mermaid flowchart (≥5 nodes)
  - core_concept_map_analysis: ≥100 chars analysis of the map
  - features: list of key features
  - key_parameters: key parameters with units
  - mathematical_model: LaTeX formulas or "无"
  - engineering_practices: ≥3 for method-type, each ≥30 chars
  - common_misconceptions: ≥2 for method-type
  - evolution: development history (≥50 chars)
  - confusion_compare: comparison table with related concepts
  - related_concepts_relations: wikilinks (≥2)
  - related_knowledge_elements: list of KE wikilinks
  - prerequisite_knowledge: wikilinks to prerequisites
  - learning_objectives: Bloom's taxonomy (≥3)
  - self_check_questions: ≥2 questions
  - solved_problem: what problem this concept solves
  - value: why this concept matters
  - upstream_downstream: upstream/downstream knowledge chains

## Execution
1. Read existing concepts.yaml for format reference
2. Write enriched concepts.yaml with all 5 concepts
3. Validate YAML syntax
4. Run pipeline: `pipeline_v2.py run --book-dir ... --book-id 01_emc_book --book-name "电磁兼容EMC技术及应用实例详解" -c 10`
