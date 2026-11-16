from . import (librarian, mission_profiler, physicist, risk_ranker, skeptic, incident_analyst,
               gap_hunter, safety_officer)

REGISTRY = {
    "librarian": librarian.run, "mission_profiler": mission_profiler.run, "physicist": physicist.run,
    "risk_ranker": risk_ranker.run, "skeptic": skeptic.run, "incident_analyst": incident_analyst.run,
    "gap_hunter": gap_hunter.run, "safety_officer": safety_officer.run,
}
