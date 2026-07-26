# Metrics catalog

Every implementation entry declares: ID, Chinese/English name, category, definition/formula, required fields/capabilities, filters, slices, minimum sample, unit/direction, personal benchmark method, built-in benchmark version, confidence and evidence selection. Missing requirements yield `unavailable`, never zero.

| ID | 中文 / English | Formula and scope | Requires | Min sample | Unit / direction |
|---|---|---|---|---:|---|
| `opening_duel_attempt_rate` | 首次交火参与率 / Opening attempt | rounds where player is in first kill / eligible rounds | core events | 5 | ratio / contextual |
| `opening_duel_win_rate` | 首次交火胜率 / Opening win | player opening kills / player opening duels | core events | 5 | ratio / high |
| `opening_death_rate` | 首死率 / Opening death | player opening deaths / eligible rounds | core events | 5 | ratio / low |
| `opening_kill_round_conversion` | 首杀回合转化 / Opening conversion | won rounds after player opening kill / such rounds | core events | 5 | ratio / high |
| `post_opening_kill_survival_rate` | 首杀后存活 / Post-opening survival | survived rounds after opening kill / such rounds | core events | 5 | ratio / high |
| `five_v_four_conversion_rate` | 5v4 转化 / 5v4 conversion | won rounds after first 5v4 / opportunities | core events | 5 | ratio / high |
| `advantage_giveback_rate` | 优势送回 / Advantage giveback | player is own next death after first advantage / opportunities | core events | 5 | ratio / low |
| `trade_opportunity_success_rate` | 补枪成功率 / Trade success | successful trades in configured window / qualified opportunities | core + estimated/real path | 8 | ratio / high |
| `isolated_death_rate` | 孤立死亡率 / Isolated deaths | non-tradeable player deaths / deaths | core + proximity | 8 | ratio / low |
| `anti_eco_loss_rate` | 反 ECO 失败率 / Anti-eco loss | lost strong-equipment rounds / anti-eco rounds | economy | 5 | ratio / low |
| `unused_utility_value_on_death` | 死亡剩余道具 / Unused utility | configured utility value remaining on death / deaths | inventory | 8 | currency / low |
| `first_shot_hit_rate` | 第一发命中率 / First-shot hit | encounters with first shot hit / shot encounters | shots + encounters | 15 | ratio / high |
| `normalized_speed_at_first_shot` | 首发归一化速度 / Normalized speed | horizontal speed / active weapon max speed | velocity + shots | 15 | ratio / low for rifles |
| `first_damage_conversion_rate` | 先伤转化率 / First-damage conversion | won encounters after dealing first damage / such encounters | damage + encounters | 15 | ratio / high |
| `multi_angle_exposure_rate` | 多角度暴露率 / Multi-angle exposure | encounters visible to 2+ enemies / visible encounters | positions + visibility | 15 | ratio / low |

Unless a better matching history slice exists, personal comparison falls back through same map/side/weapon, map/side, side, then all history. Confidence combines capability quality and a bounded sample factor. Evidence uses stable match/round/event IDs, selecting the highest-impact representative cases rather than every raw event.
