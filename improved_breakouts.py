# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# improved_breakouts.py
# pair-repeat constrant problem
# pair n students into groups of 3 thrice
# then pair n students into groups of 2 thrice
# attempt to find a schedule with no repeat pairings
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# decrease-and-conquer by working one pairing at a time
# greedy choices:
#   - start on the problematic steps, meaning:
#       - 
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

from __future__ import annotations

import argparse
import csv
import itertools
import random
import sys
import time
import traceback
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generator, List, Sequence, Tuple


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# defaults (override via args)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

DEFAULT_ATTEMPTS = 3
DEFAULT_HARD_STATES = 100
DEFAULT_TOTAL_STATES = 10_000_000

# how many candidate groupings we probe for the next exercise
FORWARDCHECK_TRIES = 6_000


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# output
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def _now() -> float:
    return time.perf_counter()

def fmt_s(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    return f"{seconds / 60:.2f} min"

def out(msg: str) -> None:
    print(msg, flush=True)

def pause_and_exit(message="\nPRESS ENTER TO CLOSE PROGRAM\n", code=0):
    try:
        input(message)
    except EOFError:
        pass
    sys.exit(code)

def order_groups_for_output(groups: List[List[int]], base_size: int) -> List[List[int]]:
    # regular groups first, then bigger groups
    regular = [g for g in groups if len(g) == base_size]
    bigger = [g for g in groups if len(g) > base_size]
    return regular + bigger


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# data
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dataclass(frozen=True)
class Student:
    idx: int
    name: str
    email: str

@dataclass(frozen=True)
class ClassInfo:
    class_name: str
    class_date: str
    facilitator: str

@dataclass(frozen=True)
class ExerciseSpec:
    label: str
    group_rule: int


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# csv
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def find_single_csv_in_folder(folder: Path) -> Path:
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"expected folder does not exist: {folder}")
    csv_files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".csv"])
    if len(csv_files) == 0:
        raise FileNotFoundError(f"no .csv files found in: {folder}")
    if len(csv_files) > 1:
        raise FileExistsError(f"expected exactly 1 .csv in {folder}, found: {[p.name for p in csv_files]}")
    return csv_files[0]

def read_loc_info_csv(path: Path) -> Tuple[ClassInfo, List[Student]]:
    students: List[Student] = []
    class_name = ""
    class_date = ""
    facilitator = ""

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"Participant Name", "Participant Email", "Class Name", "Date_af_date", "Facilitator Name"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"csv is missing expected columns: {sorted(missing)}")

        for row in reader:
            name = (row.get("Participant Name") or "").strip()
            email = (row.get("Participant Email") or "").strip()
            if not name:
                continue

            if not class_name:
                class_name = (row.get("Class Name") or "").strip()
                class_date = (row.get("Date_af_date") or "").strip()
                facilitator = (row.get("Facilitator Name") or "").strip()

            students.append(Student(idx=len(students), name=name, email=email))

    if not students:
        raise ValueError("no participants found in csv")

    return (
        ClassInfo(
            class_name=class_name or "UNKNOWN",
            class_date=class_date or "UNKNOWN",
            facilitator=facilitator or "UNKNOWN",
        ),
        students,
    )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# schedule
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def schedule_basic() -> List[ExerciseSpec]:
    return [
        ExerciseSpec("Day 1 - Exercise 1", 2),
        ExerciseSpec("Day 1 - Exercise 2", 2),
        ExerciseSpec("Day 2 - Exercise 3", 3),
        ExerciseSpec("Day 2 - Exercise 4", 3),
        ExerciseSpec("Day 3 - Exercise 5", 2),
        ExerciseSpec("Day 3 - Exercise 6", 3),
    ]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# group sizes
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def decompose_n_into_k_and_k1(n: int, k: int) -> List[int]:
    q, r = divmod(n, k)
    b = r
    a = q - r
    if a < 0:
        raise ValueError(f"cannot decompose n={n} into groups of {k} and {k+1} only")
    sizes = [k] * a + [k + 1] * b
    sizes.sort(reverse=True)
    return sizes

def compute_group_sizes(n: int, rule: int) -> List[int]:
    if rule not in (2, 3, 4, 5, 6):
        raise ValueError("rule must be 2, 3, 4, 5, or 6")
    sizes = decompose_n_into_k_and_k1(n, rule)
    if sum(sizes) != n:
        raise AssertionError(f"bad decomposition: n={n}, rule={rule}, sizes={sizes}")
    return sizes

def pairs_created_by_sizes(sizes: List[int]) -> int:
    # sum of C(s,2) over groups
    return sum((s * (s - 1)) // 2 for s in sizes)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# pair bitmasks
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def build_pair_bit_table(n: int) -> List[List[int]]:
    bits = [[0] * n for _ in range(n)]
    idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            b = 1 << idx
            bits[i][j] = b
            bits[j][i] = b
            idx += 1
    return bits

def group_is_valid_under_mask(group: Sequence[int], forbidden_mask: int, bits: List[List[int]]) -> bool:
    for a, b in itertools.combinations(group, 2):
        if forbidden_mask & bits[a][b]:
            return False
    return True


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# greedy helper
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def allowed_partner_count(s: int, remaining: Sequence[int], forbidden_mask: int, bits: List[List[int]]) -> int:
    c = 0
    for t in remaining:
        if t == s:
            continue
        if forbidden_mask & bits[s][t]:
            continue
        c += 1
    return c


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# exercise generator
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def generate_groupings_for_exercise(
    n: int,
    sizes: List[int],
    forbidden_mask: int,
    bits: List[List[int]],
    rng: random.Random,
) -> Generator[List[List[int]], None, None]:
    sizes_t = tuple(sizes)

    def rec(remaining: Tuple[int, ...], si: int) -> Generator[List[List[int]], None, None]:
        if si == len(sizes_t):
            if not remaining:
                yield []
            return

        gsize = sizes_t[si]
        if len(remaining) < gsize:
            return

        remaining_list = list(remaining)

        # pick most constrained anchor
        rng.shuffle(remaining_list)
        remaining_list.sort(key=lambda x: allowed_partner_count(x, remaining, forbidden_mask, bits))
        anchor = remaining_list[0]

        pool = [x for x in remaining if x != anchor]

        candidates: List[List[int]] = []
        for comb in itertools.combinations(pool, gsize - 1):
            group = [anchor, *comb]
            if not group_is_valid_under_mask(group, forbidden_mask, bits):
                continue
            candidates.append(group)

        if not candidates:
            return

        # prefer groups whose members have more future options
        rng.shuffle(candidates)
        candidates.sort(
            key=lambda g: -sum(allowed_partner_count(x, list(remaining), forbidden_mask, bits) for x in g)
        )

        for group in candidates:
            new_remaining = tuple(sorted(x for x in remaining if x not in group))
            for rest in rec(new_remaining, si + 1):
                yield [group] + rest

    yield from rec(tuple(range(n)), 0)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# scoring
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def better(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> bool:
    return a < b

def quad_delta(c: int) -> int:
    return 2 * c + 1


def score_plan_full(
    plan: List[List[List[int]]],
    sched: List[ExerciseSpec],
    bits: List[List[int]],
) -> Tuple[int, int, int]:
    n = len(bits)
    pair_slots = n * (n - 1) // 2

    seen_pairs_mask = 0
    pair_score = 0
    pair_conc = 0
    fair_score = 0

    pair_rep_counts = [0] * n
    pair_pair_rep_counts = [0] * pair_slots

    for ex, grouping in zip(sched, plan):
        for g in grouping:
            gg = list(g)
            for a, b in itertools.combinations(gg, 2):
                bit = bits[a][b]
                if seen_pairs_mask & bit:
                    pair_score += 1

                    pi = bit.bit_length() - 1
                    pair_conc += quad_delta(pair_pair_rep_counts[pi])
                    pair_pair_rep_counts[pi] += 1

                    fair_score += quad_delta(pair_rep_counts[a]); pair_rep_counts[a] += 1
                    fair_score += quad_delta(pair_rep_counts[b]); pair_rep_counts[b] += 1
                else:
                    seen_pairs_mask |= bit

    return pair_score, pair_conc, fair_score


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# forward checking
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def forwardcheck_exists_any_grouping(
    n: int,
    sizes: List[int],
    forbidden_mask: int,
    bits: List[List[int]],
    rng: random.Random,
    tries: int = FORWARDCHECK_TRIES,
) -> bool:
    # is there at least one valid grouping for the next exercise?
    it = generate_groupings_for_exercise(n, sizes, forbidden_mask, bits, rng)
    for _ in range(tries):
        try:
            _ = next(it)
            return True
        except StopIteration:
            return False
    return True  # found at least one within the probe budget


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# solver
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def solve_once(
    n: int,
    sched: List[ExerciseSpec],
    bits: List[List[int]],
    rng: random.Random,
    hard_states: int,
    total_states: int,
) -> Tuple[List[List[List[int]]], int, int, int, int]:
    pair_slots = n * (n - 1) // 2

    # build fail-fast exercise order
    ex_sizes = [compute_group_sizes(n, ex.group_rule) for ex in sched]
    ex_weights = [pairs_created_by_sizes(s) for s in ex_sizes]
    hard_order = sorted(range(len(sched)), key=lambda i: ex_weights[i], reverse=True)

    # baseline plan placeholder
    students = list(range(n))
    baseline: List[List[List[int]]] = []
    for ex_i in range(len(sched)):
        sizes = ex_sizes[ex_i]
        remaining = students[:]
        rng.shuffle(remaining)
        grouping = []
        idx = 0
        for gsize in sizes:
            grouping.append(remaining[idx:idx + gsize])
            idx += gsize
        baseline.append(grouping)

    b_pair, b_pair_conc, b_fair = score_plan_full(baseline, sched, bits)
    best_score: Tuple[int, int, int] = (b_pair, b_pair_conc, b_fair)
    best_plan = [g for g in baseline]

    states_checked = 0
    switched = False

    pair_rep_counts = [0] * n
    pair_pair_rep_counts = [0] * pair_slots

    # (pos_in_order, seen_mask) -> best score seen at that state
    best_at_state: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

    def rec(
        pos: int,
        seen_pairs_mask: int,
        score_pair: int,
        score_pair_conc: int,
        score_fair: int,
        plan_by_original_index: List[List[List[int]]],
        order: List[int],
    ) -> None:
        nonlocal states_checked, switched, best_plan, best_score

        states_checked += 1
        if states_checked > total_states:
            return

        soft_phase = states_checked > hard_states
        if soft_phase and not switched:
            switched = True
            out(f"\n[STEP] perfect solution not found in {hard_states:,} states, looking for second best...")

        cur_score: Tuple[int, int, int] = (score_pair, score_pair_conc, score_fair)

        if soft_phase:
            if not better(cur_score, best_score):
                return

            key = (pos, seen_pairs_mask)
            prev = best_at_state.get(key)
            if prev is not None and not better(cur_score, prev):
                return
            best_at_state[key] = cur_score

        if pos == len(order):
            if better(cur_score, best_score):
                best_score = cur_score
                best_plan = [g for g in plan_by_original_index]
            return

        ex_i = order[pos]
        ex = sched[ex_i]
        sizes = ex_sizes[ex_i]

        forbidden_mask = seen_pairs_mask if not soft_phase else 0

        next_forbidden_mask = None
        next_ex_sizes = None

        for grouping in generate_groupings_for_exercise(
            n=n,
            sizes=sizes,
            forbidden_mask=forbidden_mask,
            bits=bits,
            rng=rng,
        ):
            add_pair = 0
            add_pair_conc = 0
            add_fair = 0

            touched_s = [False] * n
            changed_s: List[Tuple[int, int]] = []

            def touch_s(i: int) -> None:
                if not touched_s[i]:
                    touched_s[i] = True
                    changed_s.append((i, pair_rep_counts[i]))

            touched_p = [False] * pair_slots
            changed_p: List[Tuple[int, int]] = []

            def touch_p(pi: int) -> None:
                if not touched_p[pi]:
                    touched_p[pi] = True
                    changed_p.append((pi, pair_pair_rep_counts[pi]))

            new_seen_mask = seen_pairs_mask

            # update scores + seen mask
            for g in grouping:
                gg = list(g)
                for a, b in itertools.combinations(gg, 2):
                    bit = bits[a][b]
                    if new_seen_mask & bit:
                        add_pair += 1

                        pi = bit.bit_length() - 1
                        touch_p(pi)
                        add_pair_conc += quad_delta(pair_pair_rep_counts[pi])
                        pair_pair_rep_counts[pi] += 1

                        touch_s(a); touch_s(b)
                        add_fair += quad_delta(pair_rep_counts[a]); pair_rep_counts[a] += 1
                        add_fair += quad_delta(pair_rep_counts[b]); pair_rep_counts[b] += 1
                    else:
                        new_seen_mask |= bit

            if not soft_phase and add_pair != 0:
                for pi, old in reversed(changed_p):
                    pair_pair_rep_counts[pi] = old
                for i, old in reversed(changed_s):
                    pair_rep_counts[i] = old
                continue

            # check next exercise feasibility under new mask
            if (not soft_phase) and (pos + 1 < len(order)):
                next_ex_i = order[pos + 1]
                next_sizes = ex_sizes[next_ex_i]
                if not forwardcheck_exists_any_grouping(
                    n=n,
                    sizes=next_sizes,
                    forbidden_mask=new_seen_mask,
                    bits=bits,
                    rng=rng,
                    tries=FORWARDCHECK_TRIES,
                ):
                    for pi, old in reversed(changed_p):
                        pair_pair_rep_counts[pi] = old
                    for i, old in reversed(changed_s):
                        pair_rep_counts[i] = old
                    continue

            # accept grouping at this exercise index
            plan_by_original_index[ex_i] = grouping

            rec(
                pos + 1,
                new_seen_mask,
                score_pair + add_pair,
                score_pair_conc + add_pair_conc,
                score_fair + add_fair,
                plan_by_original_index,
                order,
            )

            # undo counters
            for pi, old in reversed(changed_p):
                pair_pair_rep_counts[pi] = old
            for i, old in reversed(changed_s):
                pair_rep_counts[i] = old

            # early exit if perfect
            if best_score == (0, 0, 0):
                return
            if states_checked > total_states:
                return

    # allocate plan placeholder by original exercise index
    plan_by_original_index: List[List[List[int]]] = [[] for _ in range(len(sched))]

    rec(0, 0, 0, 0, 0, plan_by_original_index, hard_order)

    return best_plan, states_checked, best_score[0], best_score[1], best_score[2]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# multi-start wrapper
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def solve_multi_start(
    n: int,
    sched: List[ExerciseSpec],
    bits: List[List[int]],
    base_seed: int,
    attempts: int,
    hard_states: int,
    total_states: int,
) -> Tuple[List[List[List[int]]], int, int, int, int, int]:
    global_best_plan: List[List[List[int]]] = []
    global_best_score: Tuple[int, int, int] = (10**18, 10**18, 10**18)

    total_checked = 0
    best_attempt = -1

    for a in range(attempts):
        seed = base_seed + a
        rng = random.Random(seed)

        out(f"\n=== ATTEMPT {a+1}/{attempts} (seed={seed}) ===")
        t0 = _now()

        plan, checked, pair_score, pair_conc, fair = solve_once(
            n=n,
            sched=sched,
            bits=bits,
            rng=rng,
            hard_states=hard_states,
            total_states=total_states,
        )

        elapsed = _now() - t0
        total_checked += checked

        out(f"[STEP] attempt elapsed: {fmt_s(elapsed)} ({(elapsed * 1000.0):.2e} ms)")
        out(f"[STEP] attempt states checked: {checked:,}")
        out(f"[RESULT] repeated pairs: {pair_score:,}")
        out(f"[RESULT] pair concentration penalty: {pair_conc:,}")
        out(f"[RESULT] fairness penalty: {fair:,}")

        score = (pair_score, pair_conc, fair)
        if better(score, global_best_score):
            global_best_score = score
            global_best_plan = plan
            best_attempt = a

        if global_best_score == (0, 0, 0):
            out("[STEP] perfect solution found. stopping early.")
            break

    return global_best_plan, total_checked, global_best_score[0], global_best_score[1], global_best_score[2], best_attempt


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# reporting
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def fmt_student(students: List[Student], i: int) -> str:
    return f"{students[i].idx + 1}: {students[i].name}"

def analyze_pairs_only(
    sched: List[ExerciseSpec],
    plan: List[List[List[int]]],
) -> Dict[Tuple[int, int], List[Tuple[str, int]]]:
    pair_occ: Dict[Tuple[int, int], List[Tuple[str, int]]] = {}

    for ex, grouping in zip(sched, plan):
        for gi, g in enumerate(grouping, start=1):
            gg = sorted(g)
            for a, b in itertools.combinations(gg, 2):
                pair_occ.setdefault((a, b), []).append((ex.label, gi))

    pair_repeats = {k: v for k, v in pair_occ.items() if len(v) > 1}
    return pair_repeats

def print_plan(students: List[Student], sched: List[ExerciseSpec], plan: List[List[List[int]]]) -> None:
    out("\n=== BEST PLAN FOUND ===")
    for ex, grouping in zip(sched, plan):
        out(f"\n[PLAN] {ex.label}")

        base = ex.group_rule
        ordered = order_groups_for_output(grouping, base)

        for gi, g in enumerate(ordered, start=1):
            formatted = ", ".join(fmt_student(students, i) for i in g)
            out(f"  Group {gi:02d}: {formatted}")

def print_constraint_report(students: List[Student], sched: List[ExerciseSpec], plan: List[List[List[int]]]) -> None:
    pair_repeats = analyze_pairs_only(sched, plan)

    out("\n=== CONSTRAINT REPORT ===")
    out(f"[RESULT] repeated pairs: {len(pair_repeats):,}")

    if pair_repeats:
        out("\n[DETAIL] repeated pairs:")
        items = sorted(pair_repeats.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for (a, b), occ in items:
            who = f"{fmt_student(students, a)} + {fmt_student(students, b)}"
            where = "; ".join(f"{ex} (group {gi:02d})" for ex, gi in occ)
            out(f"  - {who} -> {where}")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# csv output
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def write_plan_csv(
    out_path: Path,
    info: ClassInfo,
    students: List[Student],
    sched: List[ExerciseSpec],
    plan: List[List[List[int]]],
    states_checked: int,
    pair_score: int,
    pair_conc_score: int,
    fair_score: int,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    idx_to_student = {s.idx: s for s in students}

    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        w.writerow(["class_name", info.class_name])
        w.writerow(["class_date", info.class_date])
        w.writerow(["facilitator", info.facilitator])
        w.writerow(["class_size", len(students)])
        w.writerow(["total_states_checked", states_checked])
        w.writerow(["pair_repeats", pair_score])
        w.writerow(["pair_concentration_penalty", pair_conc_score])
        w.writerow(["fairness_penalty", fair_score])
        w.writerow([])

        w.writerow(["exercise", "group_number", "student_number", "student_name", "student_email"])
        for ex, grouping in zip(sched, plan):
            base = ex.group_rule
            ordered = order_groups_for_output(grouping, base)

            for gi, g in enumerate(ordered, start=1):
                for i in g:
                    s = idx_to_student[i]
                    w.writerow([ex.label, gi, s.idx + 1, s.name, s.email])


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    ap.add_argument("--hard_states", type=int, default=DEFAULT_HARD_STATES)
    ap.add_argument("--total_states", type=int, default=DEFAULT_TOTAL_STATES)
    args = ap.parse_args()

    out("=== PHASE 0: Load input ===")
    script_dir = Path(__file__).resolve().parent
    csv_folder = script_dir / "PLACE CSV HERE"
    out(f"[STEP] Looking for exactly one CSV in: {csv_folder}")
    csv_path = find_single_csv_in_folder(csv_folder)
    out(f"[STEP] Using CSV: {csv_path.name}")

    t_load = _now()
    info_obj, students = read_loc_info_csv(csv_path)
    out(f"[STEP] Loaded {len(students)} students in {fmt_s(_now() - t_load)}")
    out(f"[INFO] Class: {info_obj.class_name} | Date: {info_obj.class_date} | Facilitator: {info_obj.facilitator}")

    n = len(students)
    sched = schedule_basic()
    bits = build_pair_bit_table(n)

    out("\n=== PHASE 1: Solve schedule (multi-start) ===")
    out(f"[STEP] attempts: {args.attempts:,}")
    out(f"[STEP] per-attempt hard states: {args.hard_states:,}")
    out(f"[STEP] per-attempt total states: {args.total_states:,}")

    t0 = _now()
    best_plan, total_checked, best_pair, best_pair_conc, best_fair, best_attempt = solve_multi_start(
        n=n,
        sched=sched,
        bits=bits,
        base_seed=args.seed,
        attempts=args.attempts,
        hard_states=args.hard_states,
        total_states=args.total_states,
    )
    elapsed = _now() - t0


    print_plan(students, sched, best_plan)
    print_constraint_report(students, sched, best_plan)

    out("\n=== RESULT ===")
    out(f"[INFO] class size: {len(students)}")
    out(f"[INFO] total solve elapsed: {fmt_s(elapsed)}")
    out(f"[INFO] total solve elapsed (milliseconds): {(elapsed * 1000.0):.2e} ms")
    out(f"[INFO] total states checked (all attempts): {total_checked:,}")
    out(f"[RESULT] repeated pairs: {best_pair:,}")
    out(f"[RESULT] pair concentration penalty: {best_pair_conc:,}")
    out(f"[RESULT] fairness penalty: {best_fair:,}")
    out(f"[INFO] best attempt index: {best_attempt + 1 if best_attempt >= 0 else 'N/A'}")

    out_csv = Path(__file__).resolve().parent / "output" / "breakouts_output.csv"
    write_plan_csv(
        out_path=out_csv,
        info=info_obj,
        students=students,
        sched=sched,
        plan=best_plan,
        states_checked=total_checked,
        pair_score=best_pair,
        pair_conc_score=best_pair_conc,
        fair_score=best_fair,
    )
    out(f"\n[STEP] wrote csv: {out_csv}")

    out("\n=== DONE ===")


if __name__ == "__main__":
    try:
        main()
        pause_and_exit()
    except KeyboardInterrupt:
        print("\nProgram cancelled by user!")
        pause_and_exit(code=1)
    except Exception:
        print("\n" + "~" * 33)
        traceback.print_exc()
        print("~" * 33)
        try:
            with open("error_log.txt", "a", encoding="utf-8") as f:
                f.write("\n" + "~" * 33 + "\n")
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
                traceback.print_exc(file=f)
        except Exception:
            print("UNABLE TO WRITE ERROR LOG")
        pause_and_exit(code=1)