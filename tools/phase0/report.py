def print_section(title, problems, all_good):
    print(f"== {title} ==")
    for p in problems:
        print("  -", p)
    if not problems:
        print(" ", all_good)


def print_summary(source_problems, decision_problems):
    if source_problems or decision_problems:
        print(f"\nPhase 0 NOT done: {len(source_problems)} source(s) and "
              f"{len(decision_problems)} decision(s) still open.")
        return 1
    print("\nPhase 0 done. You can start Phase 1.")
    return 0
