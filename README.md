# IntraTrack v2 — Real-Time Intramurals Scoring System

## Quick Start

```bash
pip install django
cd intratrack
python manage.py runserver
```

Open: http://127.0.0.1:8000

---

## Roles & Access

### 1. Head Committee (Admin)
- URL: http://127.0.0.1:8000/admin-panel/
- Login: `admin / admin2025`
- Can: Create facilitator accounts, assign them to sports, remove them

### 2. Facilitator (per sport)
- URL: http://127.0.0.1:8000/facilitator/
- Created by Admin via the Admin Panel
- Can:
  - Set up brackets per category (Single/Double Elimination, Round Robin)
  - Choose number of teams (generates Team A, B, C... slots)
  - Assign colleges to each team slot
  - Update scores and match status (Scheduled / Ongoing / Finished)
  - Set which match is "Up Next" for viewers

### 3. Students / Viewers
- No login needed — just open the site
- See: Now Playing, Up Next, Brackets, Standings, Schedules

---

## Sports & Categories

| Sport         | Categories                                              |
|---------------|---------------------------------------------------------|
| Basketball    | Men, Women                                              |
| Softball      | Women                                                   |
| Badminton     | Men Single, Men Doubles, Women Single, Women Doubles, Mixed |
| Sepak Takraw  | Men                                                     |
| Chess         | Men, Women                                              |
| Table Tennis  | Men Single, Men Doubles, Women Single, Women Doubles, Mixed |
| Volleyball    | Men, Women                                              |
| Soccer        | Men, Women                                              |

## Colleges
- CAF — College of Agriculture and Forestry
- CAS — College of Arts and Sciences
- CBA — College of Business Administration
- CIT — College of Industrial Technology
- CTED — College of Teacher Education
- CCJE — College of Criminal Justice Education

---

## Workflow

1. **Admin** logs in → Admin Panel → Creates facilitator for each sport
2. **Facilitator** logs in → Facilitator Dashboard → For each category:
   - Chooses bracket type + number of teams
   - Clicks "Generate Bracket" (creates Team A, B, C... slots)
   - Goes to category page → Assigns real colleges to slots
3. **During games**: Facilitator updates scores live, sets match status, flags "Up Next"
4. **Students** watch live on the homepage and sport pages — auto-refreshes every 3 seconds

---

## Bracket Types

- **Single Elimination** — lose once, you're out. Winners auto-advance.
- **Double Elimination** — losers bracket gives teams a second chance. Grand Final at the end.
- **Round Robin** — every team plays every other team. Standings ranked by W → L → Point Diff.

