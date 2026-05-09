**Scheduling Groups with Pairwise No-Repeat Constraint**

This project has 2 programs which assign students into groups across 6 excercises. The goal of this project is to create a schedule where students aren't paired together multiple times. 

There are no dependencies for this program outside of the standard Python 3 libraries - simply download the raw project, unzip it, and run from the command line.

**Baseline Algorithm:** This file is our baseline algorithm which uses a brute force approach to create the groupings of students. This program is super exponential - therefore the program will generate a projected runtime when over 1,000,000 pairings are possible for each exercise. To run our baseline algorithm `brute_force_breakouts.py` enter into command line: python brute_force_breakouts.py
Optional command line arguments: python brute_force_breakouts.py --seed 0 --estimate_after 100000 --batch_update 10000 --max_plans 500000

**Improved Algorithm:** This file is our improved alogrithm which uses a decrease-and-conquer approach, and uses a hard and soft phase to manage repeating student groupings. To run our improved algorithm `improved_breakouts.py` enter into command line: python improved_breakouts.py
defaults:
python improved_breakouts.py --seed 0
python improved_breakouts.py --attempts 3
python improved_breakouts.py --hard_states 100
python improved_breakouts.py --total_states 10000000

The file `input.csv` contains our input/student information. To set your input, insert or remove students. All participant information is required: 
- `Participant Name`
- `Participant Email`
- `Class Name`
- `Date_af_date`
- `Facilitator Name`
Student information format: Participant Name,Participant Email,Class Name,Receiving Cert,Date_af_date,Facilitator Name,eCert Link,LoC Link
Only column required for a student of n to be registered is Participant name. Note this first line of the included .csv:
```Dr. Bingo W.H. Naymo,drbingowhnaymo@gmail.com,101,FALSE,"August 24, 2025",-----,,```

## How to Generate Experimental Results
After running `brute_force_breakouts.py` The algorithm will run in 3 phases. 
=== PHASE 0: Load input ===: In phase 0 the program analyzes the CSV file which contains the input. 
=== PHASE 1: Candidate counts (theoretical) ===: In Phase 1 candidates are counted across each day adn each exercise. 
=== PHASE 2: Global brute force estimate ===: In phase 2 the estimated run time to create the groupings are created. 
=== PHASE 3: Real brute force (feasible) ===: In phase 3 the algorithm uses brute force to create the groupings and will output the results. Results should look similar to: 

```
=== PHASE 0: Load input ===
[STEP] Looking for exactly one CSV in: D:\Documents\CLCI\COACHBOT\PLACE CSV HERE
[STEP] Using CSV: input.csv
[STEP] Loaded 12 students in 0.2 ms
[INFO] Class: 101 | Date: August 24, 2025 | Facilitator: -----

=== PHASE 1: Candidate counts (theoretical) ===
[EX] Day 1 — Exercise 1: preferred=2 -> sizes=[2, 2, 2, 2, 2, 2] | candidates=10,395
[EX] Day 1 — Exercise 2: preferred=2 -> sizes=[2, 2, 2, 2, 2, 2] | candidates=10,395
[EX] Day 2 — Exercise 3: preferred=3 -> sizes=[3, 3, 3, 3] | candidates=15,400
[EX] Day 2 — Exercise 4: preferred=3 -> sizes=[3, 3, 3, 3] | candidates=15,400
[EX] Day 3 — Exercise 5: preferred=2 -> sizes=[2, 2, 2, 2, 2, 2] | candidates=10,395
[EX] Day 3 — Exercise 6: preferred=3 -> sizes=[3, 3, 3, 3] | candidates=15,400

=== PHASE 2: Global brute force estimate ===
[INFO] Candidate counts per exercise: 10,395, 10,395, 15,400, 15,400, 10,395, 15,400
[INFO] Total full 6-exercise plans (cartesian product) ≈ 4,102,377,707,291,787,000,000,000
[INFO] Estimating worst-case runtime based on first 100,000 checks, please wait...

[WARN] 100,000 full plans checked.
       Current average speed: 187,191.74 plans/sec
       Current average speed: 0.005342 ms/plan
       Best score seen during benchmark: 10

[ETA] Worst-case runtime to check every plan: 694,932,064,570 years, 2 months, 7 days, 17 hours, 6 minutes, 8 seconds
[ETA] Worst-case runtime (milliseconds): 2.19e+22 ms

=== PHASE 3: Real brute force (feasible) ===
[STEP] Generating ALL candidates for Day 1 — Exercise 1...
[STEP] Generated 10,395 candidates.
[STEP] Generating ALL candidates for Day 1 — Exercise 2...
[STEP] Generated 10,395 candidates.
[STEP] Generating ALL candidates for Day 2 — Exercise 3...
[STEP] Generated 15,400 candidates.
[STEP] Generating ALL candidates for Day 2 — Exercise 4...
[STEP] Generated 15,400 candidates.
[STEP] Generating ALL candidates for Day 3 — Exercise 5...
[STEP] Generated 10,395 candidates.
[STEP] Generating ALL candidates for Day 3 — Exercise 6...
[STEP] Generated 15,400 candidates.
[INFO] Estimating worst-case runtime based on first 100,000 checks, please wait...
[STEP] Starting GLOBAL brute force over all 6 exercises...

[WARN] 100,000 full plans checked.
Current average speed: 188,163.64 plans/sec
Estimated TOTAL runtime: 2.18E+22 ms
Worst-case remaining runtime: 691,342,614,160 years, 1 months, 6 days, 17 hours, 12 minutes, 32 seconds
Remaining plans to check: 4,102,377,707,291,786,999,900,000 (out of 4,102,377,707,291,787,000,000,000)

Checking remaining plans:   0%|     | 2210000/4102377707291786999900000 [00:12<6354020099077091:33:20, 179343.05plan/s, best_score=20]
```

After running `improved_breakouts.py` the program will take 3 attempts to generate a schedule and will keep and output the best attempt. The groupings for each student, repeated pairs, and data including the total solve time & repeated pairs are output.
This file writes: `./output/breakouts_output.csv`
End of the results should look similar to:

```
=== PHASE 0: Load input ===
[STEP] Looking for exactly one CSV in: D:\Documents\CLCI\COACHBOT\PLACE CSV HERE
[STEP] Using CSV: input.csv
[STEP] Loaded 12 students in 0.2 ms
[INFO] Class: 101 | Date: August 24, 2025 | Facilitator: -----

=== PHASE 1: Solve schedule (multi-start) ===
[STEP] attempts: 3
[STEP] per-attempt hard states: 100
[STEP] per-attempt total states: 10,000,000

=== ATTEMPT 1/3 (seed=0) ===
[STEP] attempt elapsed: 3.3 ms (3.26e+00 ms)
[STEP] attempt states checked: 7
[RESULT] repeated pairs: 0
[RESULT] pair concentration penalty: 0
[RESULT] fairness penalty: 0
[STEP] perfect solution found. stopping early.

=== BEST PLAN FOUND ===

[PLAN] Day 1 - Exercise 1
  Group 01: 4: Sage Wilson, 10: Avery Allen
  Group 02: 7: Sage Patel, 3: Logan Young
  Group 03: 8: Rowan Nguyen, 2: Reese Wilson
  Group 04: 9: Skyler Walker, 1: Dr. Bingo W.H. Naymo
  Group 05: 11: Hayden Anderson, 6: Jamie Johnson
  Group 06: 5: Morgan Taylor, 12: Sage King

[PLAN] Day 1 - Exercise 2
  Group 01: 4: Sage Wilson, 7: Sage Patel
  Group 02: 8: Rowan Nguyen, 12: Sage King
  Group 03: 6: Jamie Johnson, 5: Morgan Taylor
  Group 04: 3: Logan Young, 9: Skyler Walker
  Group 05: 10: Avery Allen, 1: Dr. Bingo W.H. Naymo
  Group 06: 2: Reese Wilson, 11: Hayden Anderson

[PLAN] Day 2 - Exercise 3
  Group 01: 3: Logan Young, 8: Rowan Nguyen, 11: Hayden Anderson
  Group 02: 4: Sage Wilson, 2: Reese Wilson, 5: Morgan Taylor
  Group 03: 6: Jamie Johnson, 9: Skyler Walker, 10: Avery Allen
  Group 04: 7: Sage Patel, 1: Dr. Bingo W.H. Naymo, 12: Sage King

[PLAN] Day 2 - Exercise 4
  Group 01: 6: Jamie Johnson, 2: Reese Wilson, 7: Sage Patel
  Group 02: 8: Rowan Nguyen, 5: Morgan Taylor, 9: Skyler Walker
  Group 03: 1: Dr. Bingo W.H. Naymo, 3: Logan Young, 4: Sage Wilson
  Group 04: 12: Sage King, 10: Avery Allen, 11: Hayden Anderson

[PLAN] Day 3 - Exercise 5
  Group 01: 2: Reese Wilson, 12: Sage King
  Group 02: 1: Dr. Bingo W.H. Naymo, 11: Hayden Anderson
  Group 03: 9: Skyler Walker, 7: Sage Patel
  Group 04: 5: Morgan Taylor, 3: Logan Young
  Group 05: 6: Jamie Johnson, 4: Sage Wilson
  Group 06: 10: Avery Allen, 8: Rowan Nguyen

[PLAN] Day 3 - Exercise 6
  Group 01: 3: Logan Young, 2: Reese Wilson, 10: Avery Allen
  Group 02: 8: Rowan Nguyen, 1: Dr. Bingo W.H. Naymo, 6: Jamie Johnson
  Group 03: 12: Sage King, 4: Sage Wilson, 9: Skyler Walker
  Group 04: 7: Sage Patel, 5: Morgan Taylor, 11: Hayden Anderson

=== CONSTRAINT REPORT ===
[RESULT] repeated pairs: 0

=== RESULT ===
[INFO] class size: 12
[INFO] total solve elapsed: 3.6 ms
[INFO] total solve elapsed (milliseconds): 3.61e+00 ms
[INFO] total states checked (all attempts): 7
[RESULT] repeated pairs: 0
[RESULT] pair concentration penalty: 0
[RESULT] fairness penalty: 0
[INFO] best attempt index: 1

[STEP] wrote csv: D:\Documents\CLCI\COACHBOT\output\breakouts_output.csv

=== DONE ===

PRESS ENTER TO CLOSE PROGRAM
```

**LIMITATIONS**
The baseline algorithm has combinatorial explosion, so it becomes infeasible with inputs that are greater than 7. Because of this limitation it takes the baseline algorithm days to fully run, therefore the baseline alorithm will instead estimate the total runtime instead of fully creating the groupings.