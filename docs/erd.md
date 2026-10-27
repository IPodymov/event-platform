# Модель данных (ERD)

Схема разбита на три диаграммы по доменам. Поля — минимальный набор из `CLAUDE.md` (раздел 5) плюс служебные. `id` (bigint) и `created_at`/`updated_at` подразумеваются у всех таблиц и показаны только там, где важны для логики. Все суммы в деньгах хранятся в копейках (`bigint`), валюта одна — RUB, все даты — в UTC.

## 1. Пользователи, дисциплины, команды, турниры

```mermaid
erDiagram
    User ||--|| Profile : has
    User ||--o{ GameAccount : owns
    Game ||--o{ GameAccount : "account for"
    Game ||--o{ MapPool : has
    MapPool ||--o{ MapPoolEntry : contains
    Game ||--o{ RulesTemplate : has

    Game ||--o{ Team : "discipline of"
    User ||--o{ Team : captains
    Team ||--o{ TeamMembership : has
    User ||--o{ TeamMembership : "member via"
    Team ||--o{ TeamInvite : sends
    User ||--o{ TeamInvite : receives

    Game ||--o{ Tournament : "played in"
    User ||--o{ Tournament : organizes
    Tournament ||--o{ TournamentStaff : "co-organized by"
    User ||--o{ TournamentStaff : "staff of"
    Tournament ||--o{ Stage : "split into"
    Tournament ||--o{ Registration : receives
    Team |o--o{ Registration : "registers as"
    User |o--o{ Registration : "registers solo as"
    Registration ||--o| CheckIn : "checked in by"
    Registration ||--o{ HearthstoneDeck : submits

    User {
        bigint id PK
        string email UK "USERNAME_FIELD, case-insensitive unique"
        string password
        bool is_active
        bool is_staff
        datetime date_joined
    }
    Profile {
        bigint user_id FK
        string nickname UK
        string avatar
        string country
        string timezone
    }
    GameAccount {
        bigint user_id FK
        bigint game_id FK
        string external_id "Steam ID64 / Riot ID / BattleTag"
        string region
        bool verified
    }
    Game {
        string slug UK "cs2, dota2, wildrift, hearthstone"
        string participant_type "solo | team"
        int roster_size
        int max_substitutes
        json allowed_series "Bo1, Bo3, Bo5"
        string result_verification "manual | opendota"
    }
    MapPool {
        bigint game_id FK
        string name
        bool is_active "one active pool per game"
    }
    MapPoolEntry {
        bigint map_pool_id FK
        string map_name
        int order
    }
    RulesTemplate {
        bigint game_id FK
        string title
        text body
    }
    Team {
        string name
        string tag
        string logo
        bigint game_id FK
        bigint captain_id FK
    }
    TeamMembership {
        bigint team_id FK
        bigint user_id FK
        bigint game_id FK "copy of team.game"
        string role "captain | player | substitute"
        datetime joined_at
        datetime left_at "null = active"
    }
    TeamInvite {
        bigint team_id FK
        bigint invitee_id FK "null for link invites"
        string token UK
        string status
        datetime expires_at
    }
    Tournament {
        bigint game_id FK
        bigint organizer_id FK
        string title
        text rules
        string region
        int max_participants
        int series_format "1 | 3 | 5"
        datetime registration_opens_at
        datetime registration_closes_at
        datetime checkin_opens_at
        datetime starts_at
        string status "draft ... completed | cancelled"
        datetime published_at "null = private draft"
    }
    TournamentStaff {
        bigint tournament_id FK
        bigint user_id FK
        string role "co_organizer"
    }
    Stage {
        bigint tournament_id FK
        int order
        string format "single_elim | double_elim | round_robin | swiss"
        json settings
    }
    Registration {
        bigint tournament_id FK
        bigint team_id FK "nullable, XOR user_id"
        bigint user_id FK "nullable, XOR team_id"
        json roster_snapshot
        int seed
        string status "registered | waitlisted | checked_in | no_show | withdrawn"
        datetime created_at "waitlist order"
    }
    CheckIn {
        bigint registration_id FK
        bigint checked_in_by_id FK
        datetime checked_in_at
    }
    HearthstoneDeck {
        bigint registration_id FK
        string deck_code
        string hero_class
    }
```

Ключевые ограничения:
- `GameAccount`: `UNIQUE(game, external_id)`.
- `TeamMembership`: денормализованное `game_id` и частичный уникальный индекс `(user, game) WHERE left_at IS NULL` — одна активная команда игрока в дисциплине; один активный капитан в команде.
- `Team`: `UNIQUE(game, lower(name))`, `UNIQUE(game, lower(tag))`.
- `Registration`: `CHECK ((team_id IS NULL) <> (user_id IS NULL))`; `UNIQUE(tournament, team)` и `UNIQUE(tournament, user)`.
- `Stage`: `UNIQUE(tournament, order)`.
- `HearthstoneDeck`: `UNIQUE(registration, hero_class)`.

## 2. Матчи, результаты, модерация, уведомления

```mermaid
erDiagram
    Stage ||--o{ Match : contains
    Registration |o--o{ Match : "participant_a / participant_b / winner"
    Match |o--o{ Match : "next_match_winner / next_match_loser"
    Match ||--o{ MatchGame : "series of"
    Match ||--o| MapVeto : has
    MapVeto ||--o{ MapVetoStep : steps
    Match ||--o{ MatchCheckIn : "ready by"
    Match ||--o{ MatchReport : "reported by"
    MatchReport ||--o{ MatchReportGame : "score per game"
    MatchReport ||--o{ Screenshot : attaches
    Match ||--o| Dispute : "contested in"
    Dispute ||--o{ DisputeEvidence : collects
    Stage ||--o{ Standing : ranks

    User ||--o{ Complaint : files
    User ||--o{ Ban : "banned by / subject of"
    User ||--o{ AuditLog : "actor of"
    User ||--o{ Notification : receives

    Match {
        bigint stage_id FK
        int round
        int position
        string bracket_side "upper | lower | grand_final | group | swiss"
        string group_label "round robin group"
        bigint participant_a_id FK "nullable"
        bigint participant_b_id FK "nullable"
        int best_of
        datetime scheduled_at
        string status "pending ... completed | disputed | forfeit"
        bigint winner_id FK "nullable"
        bigint next_match_winner_id FK "nullable"
        string next_match_winner_slot "a | b"
        bigint next_match_loser_id FK "nullable"
        string next_match_loser_slot "a | b"
    }
    MatchGame {
        bigint match_id FK
        int number
        string map "CS2"
        bigint winner_id FK
        int score_a "rounds, CS2 tie-break"
        int score_b
        string external_match_id "Dota 2"
        string deck_class_a "Hearthstone"
        string deck_class_b "Hearthstone"
    }
    MapVeto {
        bigint match_id FK
        bigint first_actor_id FK
        string status
        datetime turn_deadline
    }
    MapVetoStep {
        bigint veto_id FK
        int order
        string action "ban | pick | decider | side"
        bigint actor_id FK "null = auto by timeout"
        string map_name
        string side
    }
    MatchCheckIn {
        bigint match_id FK
        bigint registration_id FK
        datetime checked_in_at
    }
    MatchReport {
        bigint match_id FK
        bigint registration_id FK "reporting side"
        bigint submitted_by_id FK
        string status "submitted | confirmed | rejected | superseded"
        datetime submitted_at
    }
    MatchReportGame {
        bigint report_id FK
        int number
        bigint winner_id FK
        int score_a
        int score_b
        string external_match_id
        string deck_class_a
        string deck_class_b
    }
    Screenshot {
        bigint report_id FK
        string file "S3, image only, max 5 MB"
    }
    Dispute {
        bigint match_id FK
        bigint opened_by_id FK
        string status "open | resolved"
        bigint resolved_by_id FK
        bigint chosen_report_id FK "nullable"
        text resolution
    }
    DisputeEvidence {
        bigint dispute_id FK
        bigint submitted_by_id FK
        string file
        text comment
    }
    Standing {
        bigint stage_id FK
        bigint registration_id FK
        string group_label
        int wins
        int losses
        int draws
        int points
        int game_diff
        int round_diff
        int buchholz
        int rank
    }
    Complaint {
        bigint author_id FK
        string target_type
        bigint target_id
        text text
        string status
    }
    Ban {
        bigint user_id FK
        bigint issued_by_id FK
        text reason
        datetime expires_at "null = permanent"
    }
    AuditLog {
        bigint actor_id FK
        string action
        string target_type
        bigint target_id
        json before
        json after
        datetime created_at
    }
    Notification {
        bigint recipient_id FK
        string event
        json payload
        datetime read_at
    }
```

Ключевые ограничения:
- `Match`: `UNIQUE(stage, bracket_side, round, position)`; `next_match_*_slot IN ('a', 'b')`.
- `MatchGame`: `UNIQUE(match, number)`.
- `MatchReport`: одна активная (`submitted`) запись на сторону матча.
- `Standing`: `UNIQUE(stage, registration)`.

## 3. Деньги: донаты, журнал, призы, выплаты

```mermaid
erDiagram
    User |o--o{ Donation : makes
    Tournament |o--o{ Donation : "targeted by"
    LedgerTransaction ||--|{ LedgerEntry : "balanced set of"
    LedgerAccount ||--o{ LedgerEntry : "posted to"
    Tournament |o--o| LedgerAccount : "tournament_pool:<id>"
    Donation |o--o| LedgerTransaction : "settled by"
    Tournament ||--|| PrizePool : funds
    PrizePool ||--o{ PrizePlace : "split into"
    PrizePool ||--o{ Allocation : "receives from bank"
    Allocation ||--|| LedgerTransaction : "posted as"
    PrizePlace ||--o{ Payout : "paid as"
    User ||--o{ Payout : receives
    Payout ||--o| PayoutDetails : "encrypted details"
    Payout |o--o{ LedgerTransaction : "approved / paid"

    Donation {
        bigint user_id FK "nullable"
        bigint tournament_id FK "null = platform bank"
        bigint amount "kopecks"
        bool is_anonymous
        text comment
        string provider "yookassa | stripe"
        string provider_payment_id UK
        string status "pending | succeeded | canceled | refunded"
    }
    LedgerAccount {
        string code UK "provider_clearing, platform_bank, tournament_pool:<id>, ..."
        bigint cached_balance "derived, reconciled from entries"
    }
    LedgerTransaction {
        string type "donation | commission | allocation | payout | refund | reversal"
        string reference_type
        bigint reference_id
        bigint reverses_id FK "nullable, storno"
        bigint created_by_id FK
        datetime created_at
    }
    LedgerEntry {
        bigint transaction_id FK
        bigint account_id FK
        bigint amount "debit > 0, credit < 0; sum per transaction = 0"
    }
    PrizePool {
        bigint tournament_id FK
        bigint target_amount "nullable"
        string status "collecting | locked | distributed | paid | refunded"
    }
    PrizePlace {
        bigint prize_pool_id FK
        int place
        decimal share_percent "sum per pool = 100"
        bigint amount "computed at distribution"
        bigint registration_id FK "winner, set at distribution"
    }
    Allocation {
        bigint prize_pool_id FK
        bigint amount
        string rule "manual | fixed | percent"
        bigint created_by_id FK
    }
    Payout {
        bigint prize_place_id FK
        bigint recipient_id FK
        bigint amount
        bigint tax_withheld "0 until legal review"
        string kyc_status
        string status "awaiting_details ... paid | failed | cancelled"
        bigint approved_by_id FK
    }
    PayoutDetails {
        bigint payout_id FK
        bytes encrypted_details "key from env, masked in admin and logs"
    }
```

Ключевые ограничения:
- `LedgerEntry` неизменяемы (нет UPDATE/DELETE на уровне сервиса; исправление — сторно через `reverses_id`). Сумма `amount` в рамках `LedgerTransaction` = 0.
- Балансы считаются как `SUM(LedgerEntry.amount)` по счёту; `cached_balance` — только кэш, сверяемый с журналом.
- `Donation.provider_payment_id` уникален — основа идемпотентности вебхуков.
- `PrizePlace`: `UNIQUE(prize_pool, place)`.

Открытые вопросы и принятые решения ведутся в `docs/decisions.md`.
