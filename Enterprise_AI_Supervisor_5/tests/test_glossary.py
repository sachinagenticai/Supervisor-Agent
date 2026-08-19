from pathlib import Path

from supervisor_control_tower.agent_registry import AgentRegistry
from supervisor_control_tower.rules.registry import RuleRegistry
from supervisor_control_tower.agent_glossary import agent_summary_row, filter_agents


ROOT = Path(__file__).resolve().parents[1]


def _library():
    agents = AgentRegistry.from_json(ROOT / "config" / "agents.json")
    rules = RuleRegistry.from_json(agents, ROOT / "config" / "rule_packs.json")
    return agents, rules


def test_every_enabled_agent_has_complete_business_glossary():
    registry, _ = _library()
    agents = registry.list_enabled()

    assert len(agents) == 5
    for agent in agents:
        glossary = agent.glossary
        assert len(glossary.business_purpose) >= 80
        assert len(glossary.business_outcomes) >= 3
        assert len(glossary.example_use_cases) >= 3
        assert len(glossary.typical_inputs) >= 3
        assert len(glossary.typical_outputs) >= 3
        assert len(glossary.human_review_triggers) >= 3
        assert len(glossary.out_of_scope) >= 3
        assert len(glossary.operating_notes) >= 2


def test_glossary_search_matches_capability_and_use_case():
    registry, _ = _library()
    agents = registry.list_enabled()

    finops = filter_agents(agents, "rightsizing")
    assert [agent.code for agent in finops] == ["FINOPS_OPTIMIZATION"]

    document = filter_agents(agents, "obligation extraction")
    assert [agent.code for agent in document] == ["ENTERPRISE_DOCUMENT_REVIEW"]


def test_glossary_summary_uses_actual_rule_registry_counts():
    registry, rule_registry = _library()

    for agent in registry.list_enabled():
        rules = rule_registry.get_rules(agent.rule_pack_id, agent.tool_code)
        row = agent_summary_row(agent, rules)
        assert row["Agent"] == agent.name
        assert row["Controls"] == len(rules)
        assert row["Controls"] > 0
        assert row["Owner"] == agent.owner
