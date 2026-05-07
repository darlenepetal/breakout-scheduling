#!/usr/bin/env python3
"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
INTENTIONALLY AWFUL GLOBAL BRUTE FORCE (TSP-STYLE) BREAKOUT PROTOTYPE
WARNING: MAY RUN UNTIL THE SUN BECOMES TOO HOT FOR WATER TO EXIST ON EARTH
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

purpose:
- to generate breakout rooms for n students across 6 exercises where no two students
  are paired together more than once. of the 6 exercises there are:
    3 exercises in groups of 2
    3 exercises in groups of 3

what it does:
- reads ONE LoC Info-style CSV from ./PLACE CSV HERE/
- for EACH exercise, generates ALL possible groupings (partitions) that match the exercise's group-size pattern.
- then performs a GLOBAL brute-force search over the cartesian product of candidates across ALL exercises:
    plan = (choice for Ex1, choice for Ex2, ..., choice for Ex6)

scoring:
- score a full plan by counting how many student-pairs repeat across exercises.
- keep the best plan seen so far (lowest repeat count).
- stop early if a perfect plan (score == 0) is found.

progress/ETA behavior:
- before checking 100,000 full plans, show a message and do NOT show a tqdm bar.
- then compute an ETA for remaining work and print it as:
    years, months, days, hours, minutes, seconds (with commas).
- THEN start tqdm for the remaining work.
- to avoid tqdm slowing the program drastically, tqdm is updated in BATCH increments (default 10,000 plans),
  and postfix is updated only when we flush a batch.

NOTE:
here are the hurdles we face with this problem:
- so, the classic Travelling Salesman Problem (TSP) can have any number n of cities. an 
  input size of 3 < n < 6 cities would be perfectly reasonable for a travelling salesman.
  we wouldn't exactly expect him to hit 20 cities per day - he would be happy with 5.
  however, with this program's intended usage, n will almost always be 12 < n < 30.
  though, we aren't looking for a shortest path iyt of all possibilities, right?
  we're just looking for the first one that has zero invalid pairings.
  so, optimistically, we won't have to check all of them if a valid one exists.
  except...
- there are 6 exercises in total that require no duplicate pairings. 3 exercises require
  groups of 2, and 3 exercises require groups of 3. if these are not possible (ex: n = 11),
  then groups of 3 or 4 are respectively needed. therefore, it's mathematically impossible
  for n <= 11 to have zero invalid pairings between any two students in every exercise.
  n = 12 is the first time the total possible pairings between two students (12 pick 2: 66)
  is greater than the number of pairings needed across these 6 exercises. this is because 12 is
  the first n (besides 6) that cleanly divides into 2 and 3, meaning groups of 2 exercises
  require only 6 pairings between two students, and groups of 3 exercises require only
  12 pairings between two students (in each of 4 groups, there's 3 pairings between students A B and C:
  AB, AC, BC), so there are 54 (3*6 + 3*12) needed pairs betwen two students. therefore, if n < 12,
  the program will run at its worst case because it's guaranteed that it will never find an instance
  where there are no invalid pairings.
- this would be bad enough if this were the TSP, which has a growth rate of (n-1)! if the starting
  city is fixed, but this is essentially 6 TSPs in one. a very rough growth rate of this brute-force
  approach would be a staggering (n!)^6.
- the number of possible combinations for n = 11 is 19,228,907,718,433,546,875,000. my computer was
  able to check 200,000 per second, meaning it would take nearly 3 billion years to check every
  single one, in which none of them will have zero invalid pairings between two students.
- if it isn't obvious, this program is bad on purpose to show why brute-force is impossible here!
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import random
import time
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

Pair = FrozenSet[int]  # frozenset({a,b})
Grouping = Tuple[Tuple[int, ...], ...]  # canonical: sorted groups, each group sorted

MAX_CANDIDATES = 1_000_000
BENCHMARK_PLANS = 100_000


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# logging
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def safe_write(msg: str) -> None:
    if tqdm is not None:
        tqdm.write(msg)
    else:
        print(msg, flush=True)

def fmt_s(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.2f} s"
    return f"{seconds / 60:.2f} min"

def fmt_ms_scientific(ms: float) -> str:
    if ms == float("inf"):
        return "∞ ms"
    return f"{ms:,.6e} ms"

def format_duration_ymdhms_commas(seconds: float) -> str:
    if seconds < 0 or seconds == float("inf"):
        return "∞"

    sec = int(round(seconds))
    minute = 60
    hour = 60 * minute
    day = 24 * hour
    month = 30 * day
    year = 365 * day

    years, sec = divmod(sec, year)
    months, sec = divmod(sec, month)
    days, sec = divmod(sec, day)
    hours, sec = divmod(sec, hour)
    minutes, sec = divmod(sec, minute)

    return (
        f"{years:,} years, {months:,} months, {days:,} days, "
        f"{hours:,} hours, {minutes:,} minutes, {sec:,} seconds"
    )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# data
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
    preferred_group_size: int  # 2 or 3


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# csv
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def find_single_csv_in_folder(folder: Path) -> Path:
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Expected folder does not exist: {folder}")
    csv_files = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".csv"])
    if len(csv_files) == 0:
        raise FileNotFoundError(f"No .csv files found in: {folder}")
    if len(csv_files) > 1:
        raise FileExistsError(f"Expected exactly 1 .csv in {folder}, found: {[p.name for p in csv_files]}")
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
            raise ValueError(f"CSV is missing expected columns: {sorted(missing)}")

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
        raise ValueError("No participants found in CSV.")

    return (
        ClassInfo(
            class_name=class_name or "UNKNOWN",
            class_date=class_date or "UNKNOWN",
            facilitator=facilitator or "UNKNOWN",
        ),
        students,
    )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# schedule
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def schedule_basic() -> List[ExerciseSpec]:
    return [
        ExerciseSpec("Day 1 — Exercise 1", 2),
        ExerciseSpec("Day 1 — Exercise 2", 2),
        ExerciseSpec("Day 2 — Exercise 3", 3),
        ExerciseSpec("Day 2 — Exercise 4", 3),
        ExerciseSpec("Day 3 — Exercise 5", 2),
        ExerciseSpec("Day 3 — Exercise 6", 3),
    ]


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# group sizing rules (your brute-force variant)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def compute_group_sizes(n: int, preferred: int) -> List[int]:
    # preferred=2: all 2s, if odd one 3
    if preferred == 2:
        if n % 2 == 0:
            sizes = [2] * (n // 2)
        else:
            if n < 3:
                raise ValueError("cannot form pairs session with n < 3 when odd")
            sizes = [3] + [2] * ((n - 3) // 2)

    # preferred=3: use 3s; if remainder 1 -> one 4; if remainder 2 -> two 4s
    elif preferred == 3:
        r = n % 3
        if r == 0:
            sizes = [3] * (n // 3)
        elif r == 1:
            if n < 4:
                raise ValueError("cannot form triples session with n < 4")
            sizes = [4] + [3] * ((n - 4) // 3)
        else:
            if n < 8:
                raise ValueError("cannot form triples session with n < 8 under the 4+4 rule")
            sizes = [4, 4] + [3] * ((n - 8) // 3)

    else:
        raise ValueError("preferred must be 2 or 3")

    if sum(sizes) != n:
        raise AssertionError((n, preferred, sizes))

    sizes.sort(reverse=True)
    return sizes


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# counting candidates (exact)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def count_groupings(n: int, group_sizes: List[int]) -> int:
    numerator = math.factorial(n)
    denom = 1
    for s in group_sizes:
        denom *= math.factorial(s)
    counts = Counter(group_sizes)
    for _, v in counts.items():
        denom *= math.factorial(v)
    return numerator // denom


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# grouping enumeration (only when feasible)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def canonicalize_grouping(groups: List[Tuple[int, ...]]) -> Grouping:
    gg = [tuple(sorted(g)) for g in groups]
    gg.sort()
    return tuple(gg)

def enumerate_all_groupings(n: int, group_sizes: List[int]) -> List[Grouping]:
    remaining0 = tuple(range(n))
    sizes = tuple(group_sizes)
    all_groupings: Set[Grouping] = set()

    def rec(remaining: Tuple[int, ...], sizes_rem: Tuple[int, ...], built: List[Tuple[int, ...]]) -> None:
        if not sizes_rem:
            if not remaining:
                all_groupings.add(canonicalize_grouping(built))
            return

        g = sizes_rem[0]
        if len(remaining) < g:
            return

        anchor = remaining[0]
        pool = remaining[1:]

        for comb in itertools.combinations(pool, g - 1):
            group = (anchor,) + comb
            new_remaining = tuple(x for x in remaining if x not in group)
            rec(new_remaining, sizes_rem[1:], built + [group])

    rec(remaining0, sizes, [])
    return list(all_groupings)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# random grouping sampler (for benchmark when enumeration is infeasible)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def random_grouping(n: int, group_sizes: List[int], rng: random.Random) -> Grouping:
    people = list(range(n))
    rng.shuffle(people)
    groups: List[Tuple[int, ...]] = []
    idx = 0
    for s in group_sizes:
        groups.append(tuple(sorted(people[idx:idx + s])))
        idx += s
    groups.sort()
    return tuple(groups)

def pairs_in_grouping(grouping: Grouping) -> List[Pair]:
    out: List[Pair] = []
    for g in grouping:
        for a, b in itertools.combinations(g, 2):
            out.append(frozenset((a, b)))
    return out


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# benchmark checker speed (same inner mechanics as real brute-force checker)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def score_plan_via_pair_counts(plan_pairs: Sequence[Sequence[Pair]]) -> int:
    # this matches the same accounting idea used in your recursion:
    # count repeats by incrementing pair_counts and adding 1 whenever prev>=1
    pair_counts: Dict[Pair, int] = {}
    score = 0
    for pairs_list in plan_pairs:
        for p in pairs_list:
            prev = pair_counts.get(p, 0)
            if prev >= 1:
                score += 1
            pair_counts[p] = prev + 1
    return score

def benchmark_100k_plans(
    n: int,
    sched: List[ExerciseSpec],
    per_ex_sizes: List[List[int]],
    rng: random.Random,
    bench_plans: int = BENCHMARK_PLANS,
    pool_size: int = 500,
) -> Tuple[float, float]:
    safe_write(f"[INFO] Estimating worst-case runtime based on first {bench_plans:,} checks, please wait...")

    # build a pool of candidate "pairs lists" per exercise
    # this is the same data shape the real checker uses during recursion.
    candidates_pairs: List[List[List[Pair]]] = []
    for sizes in per_ex_sizes:
        pool: List[List[Pair]] = []
        for _ in range(pool_size):
            g = random_grouping(n, sizes, rng)
            pool.append(pairs_in_grouping(g))
        candidates_pairs.append(pool)

    # shuffle candidate order per exercise so we don't always traverse the same prefix
    for pool in candidates_pairs:
        rng.shuffle(pool)

    pair_counts: Dict[Pair, int] = {}
    checked = 0
    best_seen = 10**18

    t0 = time.perf_counter()

    def rec(ex_i: int, cur_score: int) -> None:
        nonlocal checked, best_seen

        if checked >= bench_plans:
            return

        if ex_i == len(candidates_pairs):
            checked += 1
            if cur_score < best_seen:
                best_seen = cur_score
            return

        for pairs_list in candidates_pairs[ex_i]:
            if checked >= bench_plans:
                return

            added = 0
            updated: List[Pair] = []

            # exact same "add" logic as the real checker
            for p in pairs_list:
                prev = pair_counts.get(p, 0)
                if prev >= 1:
                    added += 1
                pair_counts[p] = prev + 1
                updated.append(p)

            rec(ex_i + 1, cur_score + added)

            # exact same "undo" logic as the real checker
            for p in updated:
                pair_counts[p] -= 1
                if pair_counts[p] == 0:
                    del pair_counts[p]

    rec(0, 0)

    elapsed = time.perf_counter() - t0
    rate = checked / elapsed if elapsed > 0 else 0.0
    ms_per_plan = (1000.0 / rate) if rate > 0 else float("inf")

    safe_write("")
    safe_write(
        f"[WARN] {checked:,} full plans checked.\n"
        f"       Current average speed: {rate:,.2f} plans/sec\n"
        f"       Current average speed: {ms_per_plan:,.6f} ms/plan\n"
        f"       Best score seen during benchmark: {best_seen}"
    )
    safe_write("")

    return rate, elapsed


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# real brute force across cartesian product (only when feasible)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dataclass
class BestSoFar:
    score: int
    plan: Optional[List[Grouping]]

def global_bruteforce_best_plan(
    per_exercise_candidates: List[List[Grouping]],
    per_exercise_pairs: List[List[List[Pair]]],
    max_plans: Optional[int] = None,
    estimate_after: int = 100_000,
    batch_update: int = 10_000,
) -> BestSoFar:
    E = len(per_exercise_candidates)
    best = BestSoFar(score=10**18, plan=None)
    pair_counts: Dict[Pair, int] = {}

    checked_plans = 0
    t0 = time.perf_counter()

    total_plans = 1
    for c in per_exercise_candidates:
        total_plans *= max(1, len(c))
    target_plans = min(total_plans, max_plans) if max_plans is not None else total_plans

    safe_write(f"[INFO] Estimating worst-case runtime based on first {estimate_after:,} checks, please wait...")

    pbar = None
    started_pbar = False
    warned_runtime = False
    pending_updates = 0

    def start_progress_bar(remaining: int) -> None:
        nonlocal pbar, started_pbar
        if tqdm is None or remaining <= 0:
            return
        pbar = tqdm(total=remaining, desc="Checking remaining plans", unit="plan", mininterval=0.5)
        started_pbar = True
        pbar.set_postfix({"best_score": best.score})

    def flush_bar() -> None:
        nonlocal pending_updates
        if pbar is None or pending_updates <= 0:
            return
        pbar.update(pending_updates)
        pending_updates = 0
        pbar.set_postfix({"best_score": best.score})

    def rec(ex_idx: int, current_plan: List[Grouping], current_score: int) -> None:
        nonlocal checked_plans, best, warned_runtime, pending_updates

        if checked_plans >= target_plans:
            return

        if ex_idx == E:
            checked_plans += 1
            if current_score < best.score:
                best = BestSoFar(score=current_score, plan=list(current_plan))

            if (not warned_runtime) and checked_plans >= estimate_after:
                warned_runtime = True
                elapsed = time.perf_counter() - t0
                rate = checked_plans / elapsed if elapsed > 0 else 0.0
                remaining = target_plans - checked_plans

                safe_write("")
                eta_seconds = remaining / rate if rate > 0 and remaining > 0 else 0.0
                total_runtime_seconds = target_plans / rate if rate > 0 else 0.0
                safe_write(
                    f"[WARN] {estimate_after:,} full plans checked.\n"
                    f"Current average speed: {rate:,.2f} plans/sec\n"
                    f"Estimated TOTAL runtime: {Decimal(total_runtime_seconds * 1000):.2E} ms\n"
                    f"Worst-case remaining runtime: {format_duration_ymdhms_commas(eta_seconds)}\n"
                    f"Remaining plans to check: {remaining:,} (out of {target_plans:,})"
                )
                safe_write("")
                start_progress_bar(remaining)

            if started_pbar and pbar is not None:
                pending_updates += 1
                if pending_updates >= batch_update:
                    flush_bar()

            return

        for cand_idx, grouping in enumerate(per_exercise_candidates[ex_idx]):
            if checked_plans >= target_plans:
                return

            pairs_list = per_exercise_pairs[ex_idx][cand_idx]

            added_score = 0
            updated: List[Pair] = []
            for p in pairs_list:
                prev = pair_counts.get(p, 0)
                if prev >= 1:
                    added_score += 1
                pair_counts[p] = prev + 1
                updated.append(p)

            current_plan.append(grouping)
            rec(ex_idx + 1, current_plan, current_score + added_score)
            current_plan.pop()

            for p in updated:
                pair_counts[p] -= 1
                if pair_counts[p] == 0:
                    del pair_counts[p]

            if best.score == 0:
                return

    safe_write("[STEP] Starting GLOBAL brute force over all 6 exercises...")
    rec(0, [], 0)

    if pbar is not None:
        flush_bar()
        pbar.close()

    elapsed = time.perf_counter() - t0
    safe_write(f"[STEP] Done. Full plans checked: {checked_plans:,} in {fmt_s(elapsed)}")
    return best


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def main() -> None:
    ap = argparse.ArgumentParser(description="Global brute-force estimator + benchmark.")
    ap.add_argument("--max_plans", type=int, default=None)
    ap.add_argument("--estimate_after", type=int, default=BENCHMARK_PLANS)
    ap.add_argument("--batch_update", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    safe_write("=== PHASE 0: Load input ===")
    script_dir = Path(__file__).resolve().parent
    csv_folder = script_dir / "PLACE CSV HERE"
    safe_write(f"[STEP] Looking for exactly one CSV in: {csv_folder}")
    csv_path = find_single_csv_in_folder(csv_folder)
    safe_write(f"[STEP] Using CSV: {csv_path.name}")

    t_load = time.perf_counter()
    info_obj, students = read_loc_info_csv(csv_path)
    safe_write(f"[STEP] Loaded {len(students)} students in {fmt_s(time.perf_counter() - t_load)}")
    safe_write(f"[INFO] Class: {info_obj.class_name} | Date: {info_obj.class_date} | Facilitator: {info_obj.facilitator}")

    n = len(students)
    sched = schedule_basic()

    safe_write("\n=== PHASE 1: Candidate counts (theoretical) ===")
    per_ex_sizes: List[List[int]] = []
    per_ex_candidate_counts: List[int] = []
    feasible_to_enumerate = True

    for ex in sched:
        sizes = compute_group_sizes(n, ex.preferred_group_size)
        per_ex_sizes.append(sizes)

        est_count = count_groupings(n, sizes)
        per_ex_candidate_counts.append(est_count)

        safe_write(f"[EX] {ex.label}: preferred={ex.preferred_group_size} -> sizes={sizes} | candidates={est_count:,}")

        if est_count > MAX_CANDIDATES:
            feasible_to_enumerate = False

    total_plans_est = 1
    for c in per_ex_candidate_counts:
        total_plans_est *= max(1, c)

    safe_write("\n=== PHASE 2: Global brute force estimate ===")
    safe_write("[INFO] Candidate counts per exercise: " + ", ".join(f"{c:,}" for c in per_ex_candidate_counts))
    safe_write(f"[INFO] Total full 6-exercise plans (cartesian product) ≈ {total_plans_est:,}")

    # always benchmark 100k checks using the same checker mechanics
    rate, bench_elapsed = benchmark_100k_plans(
    n=n,
    sched=sched,
    per_ex_sizes=per_ex_sizes,
    rng=rng,
    bench_plans=args.estimate_after,
    )

    if rate > 0:
        eta_seconds = total_plans_est / rate
        eta_ms = eta_seconds * 1000.0

        safe_write(f"[ETA] Worst-case runtime to check every plan: {format_duration_ymdhms_commas(eta_seconds)}")
        safe_write(f"[ETA] Worst-case runtime (milliseconds): {eta_ms:,.2e} ms")
    else:
        safe_write("[WARN] benchmark rate was 0; cannot compute eta.")

    # if feasible, you can still run the true brute force
    if not feasible_to_enumerate:
        safe_write("\n[INFO] Enumeration not feasible (MAX_CANDIDATES exceeded). Skipping real brute force.")
        safe_write("=== DONE ===")
        return

    safe_write("\n=== PHASE 3: Real brute force (feasible) ===")
    per_exercise_candidates: List[List[Grouping]] = []
    per_exercise_pairs: List[List[List[Pair]]] = []

    for ex, sizes in zip(sched, per_ex_sizes):
        safe_write(f"[STEP] Generating ALL candidates for {ex.label}...")
        candidates = enumerate_all_groupings(n, sizes)
        safe_write(f"[STEP] Generated {len(candidates):,} candidates.")
        pairs_for_candidates = [pairs_in_grouping(g) for g in candidates]
        per_exercise_candidates.append(candidates)
        per_exercise_pairs.append(pairs_for_candidates)

    best = global_bruteforce_best_plan(
        per_exercise_candidates=per_exercise_candidates,
        per_exercise_pairs=per_exercise_pairs,
        max_plans=args.max_plans,
        estimate_after=args.estimate_after,
        batch_update=args.batch_update,
    )

    safe_write("\n=== BEST PLAN FOUND ===")
    safe_write(f"[RESULT] Best total repeated-pair score across all exercises: {best.score}")
    if best.plan is not None:
        for ex, grouping in zip(sched, best.plan):
            safe_write(f"\n[PLAN] {ex.label}")
            for gi, g in enumerate(grouping, start=1):
                names = ", ".join(students[i].name for i in g)
                safe_write(f"  Group {gi:02d}: {names}")

    safe_write("\n=== DONE ===")


if __name__ == "__main__":
    main()