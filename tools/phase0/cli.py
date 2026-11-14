from . import paths
from .decisions import check_decisions
from .report import print_section, print_summary
from .sources import check_sources


def main(sources_csv=paths.SOURCES_CSV, decisions_json=paths.DECISIONS_JSON):
    source_problems = check_sources(sources_csv)
    decision_problems = check_decisions(decisions_json)

    print_section("Sources", source_problems, "all sources verified")
    print_section("Decisions", decision_problems, "all decisions confirmed")
    return print_summary(source_problems, decision_problems)
