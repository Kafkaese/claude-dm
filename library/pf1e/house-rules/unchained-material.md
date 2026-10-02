# Pathfinder Unchained — Adopted Material (Overview)

- **Source:** *Pathfinder Unchained* (Paizo, 2015) · https://aonprd.com/Rules.aspx?Name=Pathfinder+Unchained&Category=Optional+Rule+Systems · class pages: https://www.aonprd.com/ClassDisplay.aspx?ItemName=Rogue+%28Unchained%29 , https://www.aonprd.com/ClassDisplay.aspx?ItemName=Monk+%28Unchained%29 , https://www.aonprd.com/ClassDisplay.aspx?ItemName=Barbarian+%28Unchained%29 · ABP: https://legacy.aonprd.com/unchained/magic/automaticBonusProgression.html · background skills: https://aonprd.com/Rules.aspx?ID=1735 · action economy: https://legacy.aonprd.com/unchained/gameplay/revisedActionEconomy.html · stamina: https://aonprd.com/Rules.aspx?ID=1901 · fractional bonuses: https://aonprd.com/Rules.aspx?ID=1726 · other systems index: https://www.d20pfsrd.com/gamemastering/other-rules/unchained-rules/
- **Publisher:** Paizo
- **Published adventure:** none
- **Retrieved:** 2026-09-30
- **Tags:** house-rule · variant rules · unchained · index

Table-wide adoption per campaign house rules ("all Unchained material"). This entry indexes every subsystem in the book. **Only the subsystems actually turned on for a campaign apply** — check that campaign's `campaign.md`/`players/session-zero.md` for which are adopted (Daredevils adopts: background skills, Automatic Bonus Progression, the three Unchained classes below, "and the rest of *Pathfinder Unchained*" — read as all of the systems below being active unless a later table ruling says otherwise).

## 1. Unchained Rogue (revised class features)
Replaces the core Rogue chassis. Rogue talents, skill list and skill points (8 + Int) are unchanged; these features are revised or new:
- **Finesse Training:** bonus Weapon Finesse at 1st. At 3rd, pick one finesse weapon type and add Dex (not Str) to its damage; pick an additional weapon at 11th and 19th.
- **Sneak Attack:** unchanged trigger (no Dex bonus to AC, or flanking), 1d6 at 1st, +1d6 every 2 levels. Ranged sneak attack limited to 30 ft.; no effect through total concealment.
- **Danger Sense** (from 3rd): +1 per 3 rogue levels to Reflex saves vs. traps and to Perception vs. ambush/surprise; stacks with Trap Sense-like effects it replaces.
- **Debilitating Injury** (4th, replaces core's later "minor magic"/talent track for this purpose): whenever sneak attack damage lands, apply one of three 1-round conditions (doesn't stack, removed by healing): **Bewildered** (-2 AC, extra -2 vs. the rogue), **Disoriented** (-2 attack rolls, extra -2 vs. the rogue), **Hampered** (speed halved, minimum 5 ft., no 5-ft. step). The penalties scale to -4/-6/-8 at 10th/16th (exact breakpoints per the class table).
- **Uncanny Dodge** (4th): can't be caught flat-footed (except vs. invisible attackers, where Dex to AC is still retained), can't be flanked by rogues of lower rogue level than itself (Improved Uncanny Dodge-equivalent folded in at a later level in some printings — verify against the table if it matters at the table).
- **Rogue's Edge** (5th, 10th, 15th, 20th): grants Skill Unlock-style bonus abilities in a chosen skill at each of those levels (ties into the Skill Unlocks subsystem below).
- Evasion (2nd) and Trapfinding (half rogue level, min +1, to find/disarm traps incl. magical ones) are retained largely as core.

## 2. Unchained Monk (revised class features)
Full BAB progression (martial chassis, d10 HD). Key changes from the core Monk:
- **Flurry of Blows:** at 1st level, as a full-round action the monk gets one extra attack at their *highest* BAB (no more stepped/reduced BAB on flurry attacks). A second bonus attack is added at 11th. Spending 1 ki point during a flurry grants a further extra unarmed attack at the highest BAB.
- **Ki pool:** gained at 3rd level, equal to 1/2 monk level + Wis modifier; from 3rd, unarmed strikes count as magic for overcoming DR.
- **Ki powers:** starting at 4th and every 2 levels after, the monk picks one ki power from a growing list (abundant step, diamond body, wholeness of body, etc.) instead of receiving those abilities on a fixed track — build customization replaces the old fixed high-level ability list.
- **AC bonus:** +1 at 4th, +1 every 4 levels after, to a max of +5 at 20th; applies even against touch attacks and while flat-footed.
- **Fast Movement:** +10 ft. at 3rd, scaling up (to +60 ft. at 18th); lost in armor or under a medium/heavy load.
- **Stunning Fist:** gained free at 1st; every 4 levels (4th/8th/12th/16th/20th) the monk can apply a different condition instead of stunned (fatigued, sickened, staggered, blinded/deafened, paralyzed), per the standard per-day uses of Stunning Fist.
- Saves and BAB use the class's own progression (full BAB; Fort/Ref as good saves, Will as core).

## 3. Unchained Summoner (revised class features + eidolon evolution system)
Feature names/levels match the core Summoner's table (Life Link, Bond Senses, Shield Ally, Maker's Call, Transposition, Aspect, Merge Forms, Twin Eidolon, Gate, etc. — see `library/pf1e/character-options/summoner-unchained-class-features.md` for the level-by-level list), but the mechanics underneath, and the eidolon itself, are substantially rebuilt:
- **Subtype selection:** at 1st level the eidolon takes a subtype (agathion, angel, archon, azata, daemon, demon, devil, div, elemental, inevitable, protean, or psychopomp), chosen permanently. Each subtype grants automatic evolutions at set levels that cost no evolution points, and restricts/unlocks certain evolutions thematically (e.g. demon vs. angel eidolons diverge mechanically).
- **Base forms:** biped (30 ft. speed, strong Will, starts with claws), quadruped (40 ft., good Reflex, bite focus), serpentine (20 ft. + climb speed, bite + tail slap); a Small-size option adjusts ability scores/attack damage.
- **Evolution pool:** a level-based points total that must be fully reallocated (not banked) each time the summoner levels up; standard evolutions cost 1-4 points depending on power, with many gated by summoner level or subtype.
- The revised **summoner spell list** removes several balance problems from the original list (no exhaustive list retrieved — check spell-by-spell if a specific spell's presence/absence matters).
- **Interaction note:** applying the *Master Summoner* archetype to the Unchained chassis is a DM ruling, not RAW — see `master-summoner.md` for the ruling made for a different campaign (not binding here; re-rule if it comes up at this table).

## 4. Unchained Barbarian (rage revision)
Removes the old ability-score-adjustment-and-recalculation rage math in favor of flat bonuses and temporary HP:
- **Rage (1st-10th):** +2 melee attack/damage (and thrown weapon damage), +2 Will saves, -2 AC, plus **2 temporary hit points per Hit Die** gained on entering rage (these are lost first, not folded into current/max HP swings).
- **Greater Rage (11th+):** bonus rises to +3, temp HP to 3/HD.
- **Mighty Rage (20th):** bonus rises to +4, temp HP to 4/HD.
- **Duration:** 4 + Con modifier rounds/day at 1st level, +2 rounds per barbarian level after. Fatigued for 1 minute after raging until **Tireless Rage** (17th) removes that fatigue.
- **Rage powers:** many are revised to work continuously while raging rather than needing separate activation/being one-shot; several of the weakest core rage powers are strengthened. Stance-type rage powers need a move action to activate and don't stack with each other.
- Uncanny Dodge (2nd) and Improved Uncanny Dodge (5th, can't be flanked except by rogues of higher level) are baked into the class table; DR progresses 1/- at 7th up to 5/- at 19th.

## 5. Background Skills
A new, separate skill-rank pool:
- **Background skill list:** Appraise, Artistry (new skill), Craft, Handle Animal, Knowledge (engineering), Knowledge (geography), Knowledge (history), Knowledge (nobility), Linguistics, Lore (new skill), Perform, Profession.
- **Everything else is an "adventuring skill"** (Acrobatics, Bluff, Climb, Diplomacy, Disable Device, Disguise, Escape Artist, Fly, Heal, Intimidate, the other Knowledges, Perception, Ride, Sense Motive, Sleight of Hand, Spellcraft, Stealth, Survival, Swim, UMD) and can only be bought with regular skill ranks.
- **Ranks:** every character gains **2 background skill ranks per level** (flat; not modified by Intelligence), usable only on background skills. Regular skill ranks can still be spent on background skills if desired, but background ranks can't buy adventuring skills.
- **Class skill tie-ins:** any class with Craft or Perform as a class skill also gets Artistry as a class skill; Lore is a class skill for everyone.

## 6. Automatic Bonus Progression (ABP)
Characters get level-based numeric bonuses automatically instead of needing +X gear, and are built/equipped assuming roughly **half normal starting wealth and WBL** (since gear no longer needs to carry these bonuses):
- **Resistance** (all saves): +1 at 3rd, +2 at 8th, +3 at 10th, +4 at 13th, +5 at 14th.
- **Armor attunement** (enhancement bonus, usable as armor or shield or split): +1 at 4th, +1/+1 at 8th, +2 at 9th, scaling up to +5-equivalent by 17th.
- **Weapon attunement** (enhancement bonus to one or more weapons): same progression/levels as armor attunement, tracked separately.
- **Deflection** (AC): +1 at 5th, +2 at 10th, +3 at 16th, +4 at 17th, +5 at 18th.
- **Mental Prowess** (+ to two of Int/Wis/Cha, player's choice) and **Physical Prowess** (+ to two of Str/Dex/Con): +2 at 6th/7th respectively, scaling to +6/+4/+2 (split across the two chosen scores) by 18th.
- **Toughening** (natural armor): +1 at 8th, up to +5 by 18th.
- **Legendary gifts:** 3 at 19th, 5 more (8 total) at 20th — narrative/mechanical capstone perks, chosen from a list.
- **What this replaces:** magic weapon/armor enhancement bonuses, stat-boosting items (belts/headbands), cloaks of resistance, rings/amulets of natural armor, and rings of protection. Those slots are freed up for on-theme magic items instead (the bonus numbers no longer need to come from gear). Special abilities (flaming, keen, etc.) can still be added to weapons/armor as normal enhancements bought separately once the attunement bonus exists, per the system's item-creation rules.
- **Gearing implication for this table:** PCs don't need to buy or hunt for a "+1 weapon" or a "cloak of resistance +1" — they already have the numbers by level. Loot and shopping should focus on special-ability items, consumables, and narrative gear rather than plain bonus-granting items.

## 7. Revised (Unchained) Action Economy
Replaces standard/move/full-round/swift/immediate actions:
- A character has **3 acts** per turn. A **simple action** costs 1 act; an **advanced action** costs 2+ acts (some large advanced actions span multiple turns, carrying committed acts over). **Free actions** cost no acts but the GM can cap how many are taken per turn.
- Out of turn, a character gets **one reaction** per round (covers what used to be immediate actions and most triggered responses).
- **Iterative attacks are discarded** under this system in favor of a single-roll multiple-attack resolution (see "Replacing Iterative Attacks," a linked sub-variant) — treat as a package with this one if adopted.
- Actions have **subtypes** (e.g. "attack actions") that determine when they provoke attacks of opportunity, replacing the old case-by-case provocation rules.
- **Note for this table:** confirm whether "all Unchained material" is meant to include this action-economy overhaul, since it's a significant combat-engine change that interacts with `scripts/combat.py`'s action model; flag this to the DM before assuming it's live in play (see Notes).

## 8. Stamina & Combat Tricks
- Any character with access to the **Combat Stamina** feat (or a class feature granting it) gets a **stamina pool** equal to base attack bonus + Constitution modifier, refreshed each time the pool is regained (e.g. per encounter/rest per the feat's text).
- Spending stamina points is not an action; a character can't spend them while unconscious, fatigued, or exhausted. Dropping to 0 stamina causes fatigue until the pool has 1+ point again.
- Nearly every combat feat (Core, APG, UC, UM, ARG, ACG) has an associated **combat trick**: an extra, situational effect purchasable by spending stamina points while using that feat, e.g. *Agile Maneuvers* — spend Dex-bonus-worth of stamina (2 points per size step) to be treated as larger for a combat maneuver check.
- This is additive: it doesn't change what a feat normally does, only adds an optional stamina-fueled upgrade.

## 9. Fractional Base Bonuses (alternate BAB/save math)
Keeps a running fractional total instead of rounding BAB/saves down every level, then rounds only for the final displayed number — mainly matters for multiclass characters:
- **BAB per level:** d6 HD classes +1/2, d8 HD classes +3/4, d10/d12 HD classes +1 (no fraction to track).
- **Saves per level:** good save progression +1/2 per level (with good saves getting an effective +2 head start baked into the math vs. poor); poor save progression +1/3 per level.
- Single-class characters get identical final numbers to the standard tables; multiclass characters end up with slightly higher BAB/saves than naive per-class-table rounding would give, fixing the standard rules' penalty for multiclassing.

## 10. Other notable variant subsystems in the book
Present in *Pathfinder Unchained* but **not explicitly named** in the campaign's house-rule list — flag to the DM/player whether these are meant to be included under "the rest of Pathfinder Unchained," since some are significant:
- **Skill Unlocks:** at 5/10/15/20 ranks in a skill, a character unlocks a bonus use for that skill (ties into Unchained Rogue's Rogue's Edge above).
- **Variant Multiclassing:** trade the feats gained at 3rd/7th/11th/15th/19th level for a package of secondary-class features from a chosen second class, without spending actual levels in it.
- **Revised/Removed Alignment:** an alternate alignment-tracking system, and a separate option to remove alignment mechanics entirely.
- **Replacing Iterative Attacks:** resolves multiple attacks from high BAB with a single roll instead of several separate attack rolls (paired with the revised action economy above).
- **Wound Thresholds/Wound Levels:** injury penalties accrue as a character takes damage, rather than full function until dying.
- **Alternate Disease and Poison rules:** treats diseases/poisons as escalating multi-stage tracks rather than single per-exposure saves.

## Notes
- All of the above is Paizo material from *Pathfinder Unchained*, matching the campaign's "all Paizo sources" allowance; no third-party content involved.
- Exact per-level tables above were compiled from Archives of Nethys and legacy AoN pages; where a specific number matters at the table (e.g. an exact Debilitating Injury breakpoint, an exact ABP value at an odd level, or precise wording of a rage power change), re-verify the specific entry before it's load-bearing (e.g. before letting a build rely on it).
- **Open question for the DM:** confirm whether items 7 (revised action economy) and 10's sub-list are actually wanted; `scripts/combat.py` currently models the standard standard/move/swift/full-round action economy, and switching to the 3-acts system would need script support before it could be run at the table as written.
